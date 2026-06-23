"""
Final agent: Translation layer from mathematical outputs to human-readable action plans.

The upstream agents produce raw math:
  - Triage    → closure_prob: 0.82, dur_minutes: 142.3
  - Spatial   → diversion_path: [[12.97, 77.59], ...], affected_edges: [...]
  - Logistics → officer_assignments: [{"station": "Peenya", "officers": 6}]

This agent translates into language a dispatcher and citizen can act on:
  - "URGENT: Deploy 6 officers from Peenya PS to Tumkur Road"
  - "Expect 2-3 hour delays. Avoid Tumkur Road. Use Bellary Road via NH44."
  - Step-by-step per-station instructions

This agent contains ZERO ML, ZERO graph computation, ZERO ILP solving.
Pure data transformation — PlanState in, human-readable dict out.

WHY A DEDICATED TRANSLATION AGENT:
──────────────────────────────────
- Triage/Spatial/Logistics produce mathematically correct but operationally
  opaque outputs. A dispatcher cannot act on closure_prob=0.82.
- Separation of concerns: optimization agents never contain string formatting
  or UX logic. Directive never contains math.
- This boundary makes both sides independently testable — unit test the
  directive agent with mock PlanState without running LightGBM or OR-Tools.

WHY PYDANTIC MODEL NOT DICT:
────────────────────────────
- Frontend keys on specific field names. Dict has no schema contract — typo
  in key name fails silently at runtime.
- Pydantic model fails loudly at construction time.
- FastAPI serializes Pydantic models automatically — no manual json.dumps().
"""

import asyncio
import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.core.state import PlanState
from app.core.config import get_settings


log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# OUTPUT MODEL
# ════════════════════════════════════════════════════════════════════════════


class DirectiveOutput(BaseModel):
    """
    Human-readable action plan translated from mathematical optimization.

    Attributes:
        headline: One-liner summary (e.g., "URGENT: tree_fall — deploying 6 officers").
        severity_label: Dispatch urgency tier (High/Medium/Low/Escalated).
        citizen_alert: SMS-safe alert text (<160 chars) for public broadcast.
        dispatcher_instructions: Numbered step-by-step instructions per station.
        estimated_clearance: Human-readable duration (e.g., "~2h 22m").
        total_officers_deployed: Sum of officers assigned (0 if escalated).
        total_barricades: Barricade units deployed.
        feasibility_warning: None if fully feasible; error message if degraded.
    """

    headline: str
    severity_label: Literal["High", "Medium", "Low", "Escalated"]
    citizen_alert: str
    dispatcher_instructions: list[str]
    estimated_clearance: str
    total_officers_deployed: int
    total_barricades: int
    feasibility_warning: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# DIRECTIVE AGENT
# ════════════════════════════════════════════════════════════════════════════


class DirectiveAgent:
    """Translation layer: mathematical optimization → human-readable action plan."""

    # Severity prefix mapping (move to config.yaml when settings schema extended)
    SEVERITY_PREFIX = {
        "High": "URGENT",
        "Medium": "ADVISORY",
        "Low": "NOTICE",
    }

    def run(self, state: PlanState) -> DirectiveOutput:
        """
        Generate a human-readable directive from the complete PlanState.

        Routing logic uses guard clauses, not nested if/else:
          1. If escalated: escalation directive (mutual aid required).
          2. If logistics invalid: degraded directive (confidence warning).
          3. Otherwise: full directive (standard operations).

        WHY GUARD CLAUSE ROUTING:
          - Each state is qualitatively different, not just quantitatively.
          - Escalation is not "low confidence" — fundamentally different
            operational situation requiring different language and procedures.
          - Guard clauses make routing explicit and readable.
            Nested if/else buries escalation 3 levels deep.

        Args:
            state: Fully populated PlanState after supervisor approval.

        Returns:
            DirectiveOutput with all fields populated.

        Raises:
            ValueError: If state.triage is None (invalid pipeline order).
        """
        if state.triage is None:
            raise ValueError(
                "DirectiveAgent called before TriageAgent — invalid pipeline order"
            )

        if state.escalated:
            return self._build_escalation_directive(state)

        if not self._is_logistics_valid(state):
            return self._build_degraded_directive(state)

        return self._build_full_directive(state)

    def _build_full_directive(self, state: PlanState) -> DirectiveOutput:
        """Build directive for fully feasible plan."""
        severity = state.triage.severity_tier
        cause = state.incident.cause
        officers = state.logistics.total_officers if state.logistics else 0

        headline = self._build_headline(severity, cause, officers)
        citizen_alert = self._build_citizen_alert(
            severity,
            cause,
            getattr(state.incident, "corridor", "affected area"),
            self._format_duration(state.triage.predicted_duration_minutes),
        )
        dispatcher_instructions = self._build_dispatcher_instructions(
            state.logistics.assignments if state.logistics else [],
            f"{state.incident.lat}, {state.incident.lng}",
            state.spatial.diversion_path if state.spatial else None,
        )
        estimated_clearance = self._format_duration(
            state.triage.predicted_duration_minutes
        )

        return DirectiveOutput(
            headline=headline,
            severity_label=severity,
            citizen_alert=citizen_alert,
            dispatcher_instructions=dispatcher_instructions,
            estimated_clearance=estimated_clearance,
            total_officers_deployed=officers,
            total_barricades=state.logistics.total_barricades
            if state.logistics
            else 0,
            feasibility_warning=None,
        )

    def _build_escalation_directive(self, state: PlanState) -> DirectiveOutput:
        """Build directive when resources exhausted (mutual aid required)."""
        severity = state.triage.severity_tier
        return DirectiveOutput(
            headline="ESCALATION REQUIRED: Insufficient local resources",
            severity_label="Escalated",
            citizen_alert="ALERT: Severe congestion. Avoid area. Updates will follow.",
            dispatcher_instructions=[
                "1. Contact adjacent zone commanders for mutual aid.",
                "2. Escalate to city traffic control center.",
                "3. Consider rerouting traffic via alternate corridors.",
            ],
            estimated_clearance="Unknown — manual intervention required",
            total_officers_deployed=0,
            total_barricades=0,
            feasibility_warning="No stations within expanded search radius. Mutual aid required.",
        )

    def _build_degraded_directive(self, state: PlanState) -> DirectiveOutput:
        """Build directive with confidence warning (greedy fallback used)."""
        full_directive = self._build_full_directive(state)
        full_directive.feasibility_warning = (
            "Plan uses reduced resource allocation (greedy solver). "
            "Monitor field execution closely."
        )
        return full_directive

    def _build_dispatcher_instructions(
        self,
        assignments: list[dict],
        incident_address: str,
        diversion_path: list | None = None,
    ) -> list[str]:
        """Build numbered step-by-step instructions per station."""
        if not assignments:
            return ["No officer assignments available. Escalation pending."]

        instructions = []
        for i, assign in enumerate(assignments, 1):
            station = assign.get("station_name", assign.get("station_id", ""))
            officers = assign.get("officers_assigned", 0)
            eta = assign.get("estimated_arrival_min")
            eta_str = f"~{int(eta)} min" if eta else "ETA unknown"

            route = (
                "Approach via diversion route. Set barricades on arrival."
                if diversion_path
                else "Approach via nearest available route."
            )

            instructions.append(
                f"{i}. {station}: Dispatch {officers} officers to {incident_address}. "
                f"ETA {eta_str}. {route}"
            )

        return instructions

    def _build_citizen_alert(
        self,
        severity: str,
        cause: str,
        corridor: str,
        duration_display: str,
    ) -> str:
        """Build SMS-safe alert text (<160 chars)."""
        alert = (
            f"TRAFFIC ALERT: {cause} on {corridor}. "
            f"Expect {duration_display}. Avoid area, use alternate routes."
        )

        if len(alert) > 160:
            log.warning(f"Citizen alert exceeds 160 chars: {len(alert)}")
            alert = alert[:157] + "..."

        return alert

    def _format_duration(self, dur_minutes: float) -> str:
        """Convert float minutes to human-readable 'Xh Ym' string."""
        if dur_minutes < 0:
            return "Unknown"
        if dur_minutes < 60:
            return f"~{int(dur_minutes)} min"
        if dur_minutes >= 480:
            return f"{int(dur_minutes // 60)}h+"
        hours = int(dur_minutes // 60)
        minutes = int(dur_minutes % 60)
        return f"~{hours}h {minutes}m"

    def _build_headline(self, severity: str, cause: str, officers: int) -> str:
        """Build one-liner headline with severity prefix."""
        prefix = self.SEVERITY_PREFIX.get(severity, "NOTICE")
        return f"{prefix}: {cause} — deploying {officers} officers"

    def _is_logistics_valid(self, state: PlanState) -> bool:
        """Check if logistics output is present and feasible."""
        if state.logistics is None:
            return False
        return state.logistics.feasible


# ════════════════════════════════════════════════════════════════════════════
# ASYNC WRAPPER FOR GENERATOR
# ════════════════════════════════════════════════════════════════════════════


async def _generate_directive(state: PlanState) -> PlanState:
    """
    Async wrapper for DirectiveAgent.run().

    Runs DirectiveAgent in a thread to keep the event loop free,
    then attaches the DirectiveOutput to state.

    WHY asyncio.to_thread():
      - DirectiveAgent.run() is synchronous and CPU-bound (string
        formatting, list comprehensions). Running it directly in an
        async function blocks the event loop.
      - asyncio.to_thread() offloads to threadpool, keeping loop
        responsive for other requests.

    Args:
        state: Fully populated PlanState after supervisor approval.

    Returns:
        PlanState with state.directive populated.
    """
    agent = DirectiveAgent()
    directive = await asyncio.to_thread(agent.run, state)
    return state.model_copy(update={"directive": directive})