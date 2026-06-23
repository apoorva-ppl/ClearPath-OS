# Recursive retry-loop logic
# app/agents/supervisor.py
"""
Agent 4: Deterministic Feasibility & Escalation Decision Engine.

This is NOT an LLM loop. It reads typed Pydantic fields and applies
deterministic logic to decide: Approve → Expand → Escalate.

Why deterministic instead of LLM-as-judge:
  - An LLM can hallucinate feasibility ("the plan looks sound") even
    when logistics.feasible=False is explicitly True in the state object.
    A deterministic supervisor reads typed booleans — it cannot hallucinate.
  - Every expansion produces a structured log entry with exact retry count,
    creating a full audit trail for public-safety accountability.
  - Termination is guaranteed: max_expansion_attempts is a hard ceiling.
    An LLM loop can spin indefinitely (e.g., "try once more...").

Decision Flow (deterministic, no nested if/else):
  1. Is plan feasible? → APPROVE (stage="complete")
  2. Is plan infeasible but expandable? → EXPAND (stage="spatial")
  3. Is plan infeasible and max attempts breached? → ESCALATE (stage="failed")

Critical Contract:
  - The supervisor NEVER calls other agents directly (no triage(),
    spatial(), logistics() calls in this file).
  - It only modifies PlanState fields via .advance().
  - The generator (core/generator.py) owns the re-run loop.
  - This separation guarantees: pipeline terminates in ≤ (max_attempts + 1)
    cycles and produces an auditable trace of every decision.
"""

import logging
from typing import Any

from app.core.config import get_settings
from app.core.state import (
    PlanState,
    SpatialOutput,
    SupervisorDecision,
)


logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# FEASIBILITY CHECKING
# ════════════════════════════════════════════════════════════════


def _is_plan_feasible(state: PlanState) -> bool:
    """
    Multi-condition feasibility check.

    Returns True only if ALL of the following hold:
      - Logistics output exists and is feasible.
      - Spatial output exists with a valid diversion path.
      - Supervisor decision exists (i.e., supervisor has run ≥1 time).

    Why multi-condition instead of just logistics.feasible:
      - A logistics solution is meaningless without a valid diversion
        path. Checking both prevents partial-success silent failures.

    Args:
        state: Current PlanState.

    Returns:
        True if all prerequisites are met for a complete plan.
    """
    if state.logistics is None or not state.logistics.feasible:
        return False
    if state.spatial is None or len(state.spatial.diversion_path) == 0:
        return False
    if state.supervisor is None:
        return False
    return True


# ════════════════════════════════════════════════════════════════
# EXPANSION ELIGIBILITY
# ════════════════════════════════════════════════════════════════


def _can_expand(state: PlanState, settings: Any) -> bool:
    """
    Check if another expansion attempt is allowed.

    Args:
        state: Current PlanState with supervisor decision.
        settings: Configuration with max_expansion_attempts.

    Returns:
        True if retry_count < max_expansion_attempts.
    """
    max_attempts = settings.supervisor.max_expansion_attempts
    current_count = state.supervisor.retry_count
    return current_count < max_attempts


# ════════════════════════════════════════════════════════════════
# SPATIAL EXPANSION BUILDER
# ════════════════════════════════════════════════════════════════


def _build_expanded_spatial(
    state: PlanState,
    settings: Any,
) -> SpatialOutput:
    """
    Create a new SpatialOutput with expanded buffer radius.

    Resets diversion_path and baseline_path to empty lists to signal
    the generator that re-routing is needed. Stale paths from a smaller
    radius are geometrically invalid at the expanded radius.

    Args:
        state: Current PlanState with spatial output.
        settings: Configuration with radius_expansion_multiplier.

    Returns:
        New SpatialOutput with expanded radius and cleared paths.
    """
    old_spatial = state.spatial
    multiplier = settings.supervisor.radius_expansion_multiplier
    new_radius = old_spatial.current_buffer_radius_m * multiplier

    return SpatialOutput(
        baseline_path=[],  # Signal re-routing needed
        diversion_path=[],  # Signal re-routing needed
        current_buffer_radius_m=new_radius,
        nodes_affected=old_spatial.nodes_affected,
    )


# ════════════════════════════════════════════════════════════════
# DECISION BUILDERS
# ════════════════════════════════════════════════════════════════


def _build_escalation_decision(
    state: PlanState,
    reason: str,
) -> SupervisorDecision:
    """
    Build an escalation decision to be reviewed by a human commander.

    When escalated, the human commander can:
      - Manually adjust resource allocations.
      - Override the buffer radius.
      - Combine this incident with adjacent ones into a unified response.
      - Request additional support from neighboring jurisdictions.

    Args:
        state: Current PlanState.
        reason: Descriptive string explaining why escalation is needed.

    Returns:
        SupervisorDecision with should_escalate=True.
    """
    return SupervisorDecision(
        should_escalate=True,
        escalation_reason=reason,
        retry_count=state.supervisor.retry_count,
        expansion_applied=False,
    )


def _build_expansion_decision(state: PlanState) -> SupervisorDecision:
    """
    Build a decision to retry with expanded buffer radius.

    The generator will re-invoke spatial and logistics agents with
    the new (larger) buffer.

    Args:
        state: Current PlanState.

    Returns:
        SupervisorDecision with should_escalate=False and
        retry_count incremented.
    """
    return SupervisorDecision(
        should_escalate=False,
        escalation_reason=None,
        retry_count=state.supervisor.retry_count + 1,
        expansion_applied=True,
    )


def _build_approval_decision(state: PlanState) -> SupervisorDecision:
    """
    Build an approval decision for a feasible plan.

    Args:
        state: Current PlanState.

    Returns:
        SupervisorDecision with should_escalate=False,
        marking the plan as approved.
    """
    return SupervisorDecision(
        should_escalate=False,
        escalation_reason=None,
        retry_count=state.supervisor.retry_count,
        expansion_applied=False,
    )


# ════════════════════════════════════════════════════════════════
# STRUCTURED LOGGING
# ════════════════════════════════════════════════════════════════


def _log_supervisor_decision(
    plan_id: str,
    decision: str,
    retry_count: int,
    radius_m: float,
) -> None:
    """
    Log supervisor decision with structured fields.

    Uses the logging module (not print) so output is captured by
    log aggregators (Datadog, CloudWatch, ELK). Structured fields
    enable filtering: "show all EXPANSION events for plan_id X".

    Args:
        plan_id: Unique plan identifier for tracing.
        decision: One of "APPROVE", "EXPAND", "ESCALATE".
        retry_count: Current retry attempt number.
        radius_m: Current buffer radius in meters.
    """
    if decision == "APPROVE":
        logger.info(
            "Supervisor decision",
            extra={
                "plan_id": plan_id,
                "decision": decision,
                "retry_count": retry_count,
                "radius_m": radius_m,
            },
        )
    else:
        logger.warning(
            "Supervisor decision",
            extra={
                "plan_id": plan_id,
                "decision": decision,
                "retry_count": retry_count,
                "radius_m": radius_m,
            },
        )


# ════════════════════════════════════════════════════════════════
# SUPERVISOR AGENT
# ════════════════════════════════════════════════════════════════


class SupervisorAgent:
    """
    Deterministic feasibility and escalation decision engine.

    Single responsibility: read PlanState, apply typed-field logic,
    and return a new PlanState with updated stage and supervisor
    decision fields.

    Critical Contract:
      - Never calls other agents directly (no triage(), spatial(),
        logistics() in this class).
      - Only modifies PlanState via .advance().
      - The generator (app/core/generator.py) owns the re-run loop
        and enforces max_expansion_attempts as a hard ceiling.
      - This separation guarantees termination in ≤ (max_attempts + 1)
        cycles and produces an auditable trace of all decisions.

    Attributes:
        settings: Loaded configuration object.
    """

    def __init__(self, settings: Any) -> None:
        """
        Initialize SupervisorAgent with configuration.

        Args:
            settings: app.core.config.Settings object.
        """
        self.settings = settings

    async def check_and_adapt(self, state: PlanState) -> PlanState:
        """
        Evaluate plan feasibility and decide: Approve, Expand, or Escalate.

        Decision Table:
          ┌─────────────────────┬──────────────┬──────────────────┐
          │ Condition           │ Action       │ Return Stage     │
          ├─────────────────────┼──────────────┼──────────────────┤
          │ Feasible            │ Approve      │ "complete"       │
          │ Infeasible + Expand │ Expand       │ "spatial"        │
          │ Infeasible + Max    │ Escalate     │ "failed"         │
          └─────────────────────┴──────────────┴──────────────────┘

        Args:
            state: Current PlanState with triage, spatial, and
                logistics outputs.

        Returns:
            New PlanState with updated supervisor decision and stage.
            - "complete": plan is approved, ready for dispatch.
            - "spatial": generator will re-invoke spatial + logistics
              with expanded buffer radius.
            - "failed": plan is infeasible and max attempts reached;
              escalate to human commander.
        """
        # Initialize supervisor decision if not yet run
        if state.supervisor is None:
            state = state.advance(supervisor=SupervisorDecision(
                should_escalate=False,
                retry_count=0,
                expansion_applied=False,
            ))

        # BRANCH 1: Feasible → Approve
        if _is_plan_feasible(state):
            decision = _build_approval_decision(state)
            _log_supervisor_decision(
                state.plan_id,
                "APPROVE",
                decision.retry_count,
                state.spatial.current_buffer_radius_m,
            )
            return state.advance(supervisor=decision, stage="complete")

        # BRANCH 2: Infeasible but expandable → Expand
        if _can_expand(state, self.settings):
            decision = _build_expansion_decision(state)
            expanded_spatial = _build_expanded_spatial(state, self.settings)
            _log_supervisor_decision(
                state.plan_id,
                "EXPAND",
                decision.retry_count,
                expanded_spatial.current_buffer_radius_m,
            )
            return state.advance(
                supervisor=decision,
                spatial=expanded_spatial,
                stage="spatial",
            )

        # BRANCH 3: Infeasible and max attempts reached → Escalate
        max_attempts = self.settings.supervisor.max_expansion_attempts
        reason = (
            f"Max expansion attempts ({max_attempts}) reached. "
            f"No feasible logistics solution found. Escalating to human commander."
        )
        decision = _build_escalation_decision(state, reason)
        _log_supervisor_decision(
            state.plan_id,
            "ESCALATE",
            decision.retry_count,
            state.spatial.current_buffer_radius_m,
        )
        return state.advance(supervisor=decision, stage="failed")


# ════════════════════════════════════════════════════════════════
# MODULE FACTORY
# ════════════════════════════════════════════════════════════════


def create_supervisor_agent(settings: Any | None = None) -> SupervisorAgent:
    """
    Factory function: construct a fully-initialized SupervisorAgent.

    Args:
        settings: Configuration object. Defaults to get_settings() if None.

    Returns:
        Ready-to-use SupervisorAgent instance.
    """
    if settings is None:
        settings = get_settings()
    return SupervisorAgent(settings)