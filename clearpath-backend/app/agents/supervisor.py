import logging
from typing import Any

from app.core.config import get_settings
from app.core.state import (
    PlanState,
    SpatialOutput,
    SupervisorDecision,
)

logger = logging.getLogger(__name__)

def _is_plan_feasible(state: PlanState) -> bool:
    if state.logistics is None or not state.logistics.feasible:
        return False
    if state.spatial is None or len(state.spatial.diversion_path) == 0:
        return False
    if state.supervisor is None:
        return False
    return True

def _can_expand(state: PlanState, settings: Any) -> bool:
    max_attempts = settings.supervisor.max_expansion_attempts
    current_count = state.supervisor.retry_count
    return current_count < max_attempts

#When expansion is triggered, the Supervisor increases the search radius and clears the old routes so that the Spatial Agent recalculates a fresh plan
def _build_expanded_spatial(
    state: PlanState,
    settings: Any,
) -> SpatialOutput:

    old_spatial = state.spatial
    multiplier = settings.supervisor.radius_expansion_multiplier
    new_radius = old_spatial.current_buffer_radius_m * multiplier

    return SpatialOutput(
        baseline_path=[],  # Signal re-routing needed
        diversion_path=[],  # Signal re-routing needed
        current_buffer_radius_m=new_radius,
        nodes_affected=old_spatial.nodes_affected,
    )

def _build_escalation_decision(
    state: PlanState,
    reason: str,
) -> SupervisorDecision:
  
    return SupervisorDecision(
        should_escalate=True,
        escalation_reason=reason,
        retry_count=state.supervisor.retry_count,
        expansion_applied=False,
    )


def _build_expansion_decision(state: PlanState) -> SupervisorDecision:

    return SupervisorDecision(
        should_escalate=False,
        escalation_reason=None,
        retry_count=state.supervisor.retry_count + 1,
        expansion_applied=True,
    )


def _build_approval_decision(state: PlanState) -> SupervisorDecision:
   
    return SupervisorDecision(
        should_escalate=False,
        escalation_reason=None,
        retry_count=state.supervisor.retry_count,
        expansion_applied=False,
    )
#for monitoring n debugging
def _log_supervisor_decision(
    plan_id: str,
    decision: str,
    retry_count: int,
    radius_m: float,
) -> None:
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

#main function
class SupervisorAgent:

    def __init__(self, settings: Any) -> None:
    
        self.settings = settings

    async def check_and_adapt(self, state: PlanState) -> PlanState:
     
        # Initialize supervisor decision if not yet run
        if state.supervisor is None:
            state = state.advance(supervisor=SupervisorDecision(
                should_escalate=False,
                retry_count=0,
                expansion_applied=False,
            ))

        # BRANCH 1:everything is good ->Approve , workflow=complete
        if _is_plan_feasible(state):
            decision = _build_approval_decision(state)
            _log_supervisor_decision(
                state.plan_id,
                "APPROVE",
                decision.retry_count,
                state.spatial.current_buffer_radius_m,
            )
            return state.advance(supervisor=decision, stage="complete")

        # BRANCH 1:plan failed ->retry ->reset routes, self healing loop, stage =Expand
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

        # BRANCH 3: multiple retries ->no solution , escalate for human command , stage=Failed
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

def create_supervisor_agent(settings: Any | None = None) -> SupervisorAgent:

    if settings is None:
        settings = get_settings()
    return SupervisorAgent(settings)