import asyncio
import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.core.state import PlanState
from app.core.config import get_settings

log = logging.getLogger(__name__)

#pydantic model , defines what frontend should recieve
class DirectiveOutput(BaseModel):
    headline: str
    severity_label: Literal["High", "Medium", "Low", "Escalated"]
    citizen_alert: str
    dispatcher_instructions: list[str]
    estimated_clearance: str
    total_officers_deployed: int
    total_barricades: int
    feasibility_warning: str | None = None

class DirectiveAgent:
    SEVERITY_PREFIX = {
        "High": "URGENT",
        "Medium": "ADVISORY",
        "Low": "NOTICE",
    }
    #main function
    def run(self, state: PlanState) -> DirectiveOutput:
        if state.triage is None:
            raise ValueError(
                "DirectiveAgent called before TriageAgent — invalid pipeline order"
            )
         #branch 1 -> escalation req
        if state.escalated:
            return self._build_escalation_directive(state)
         #branch 2 -> greedy instead of ILP (output with a warning of "Reduced Confidence" or "Degrade Directive")
        if not self._is_logistics_valid(state):
            return self._build_degraded_directive(state) #when used greedy instead of ILP
         #branch 3-> generate normal plan
        return self._build_full_directive(state)
      
    def _build_full_directive(self, state: PlanState) -> DirectiveOutput:

        severity = state.triage.severity_tier
        cause = state.incident.cause
        officers = state.logistics.total_officers if state.logistics else 0

        #Example Headline:- road accident , deploy 20 officers
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

async def _generate_directive(state: PlanState) -> PlanState:
    agent = DirectiveAgent()
    directive = await asyncio.to_thread(agent.run, state)
    return state.model_copy(update={"directive": directive})