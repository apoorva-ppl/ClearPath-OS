# SSE Async Generator (The Orchestrator)
"""
Core Orchestrator: Async State Machine for Disaster Response Pipeline.

WHY ASYNC GENERATOR + SSE (not WebSocket or standard request-response)?
───────────────────────────────────────────────────────────────────────

1. **SSE is strictly server→client (unidirectional)**
   - No handshake overhead or connection state management.
   - Works over plain HTTP/1.1 (no WebSocket upgrade needed).
   - Perfect for step-by-step progress streams where the client
     never sends mid-stream commands.

2. **WebSocket is overkill for read-only progress**
   - Bidirectional communication adds complexity and harder load-balancing.
   - Full-duplex framing overhead unnecessary for one-way updates.
   - Requires persistent connection management on both sides.

3. **Standard request-response creates poor UX**
   - Pipeline takes 2-10 seconds. Holding connection with no response
     appears broken to users (blank screen).
   - SSE streams each agent result as it completes — system feels
     instant even on slow hardware.
   - Yielding prevents buffering entire plan in memory; each result
     is transmitted the moment it's ready.

This module is the single orchestration point for the entire 4-agent
pipeline, owning state machine logic, supervisor loop, and SSE events.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator
from pathlib import Path

from app.core.config import get_settings, Settings
from app.core.state import PlanState, IncidentInput, CityState
from app.core.state import ModelArtifacts
from app.core.directive import generate_directive, synthesize_dispatch_audio
from app.agents.triage import TriageAgent
from app.agents.spatial import SpatialAgent
from app.agents.logistics import LogisticsAgent
from app.agents.supervisor import SupervisorAgent


logger = logging.getLogger(__name__)


async def stream_incident_plan(
    incident: IncidentInput,
    artifacts: "ModelArtifacts",
    city_state: CityState,
) -> AsyncGenerator[str, None]:
    """
    Orchestrate the 4-agent disaster response pipeline via SSE.

    This async generator sequences an incident through Triage → Spatial →
    Logistics → Supervisor (loop). The Supervisor loop wraps only Spatial +
    Logistics because:

    WHY Triage runs outside the loop:
      - Severity prediction depends only on incident features (lat, lng, cause,
        priority), not on spatial geometry or feasibility.
      - Re-running would be redundant and would change severity mid-retry,
        violating the immutable state contract.

    WHY Spatial + Logistics loop under Supervisor:
      - If logistics is infeasible (no station in range), we expand the
        buffer radius to enlarge the search area.
      - Expanding radius changes the spatial graph (Spatial re-runs) and
        therefore the feasible allocation (Logistics re-runs).
      - Triage remains unchanged because the severity tier is independent
        of spatial geometry.

    Args:
        incident: Raw incident input (location, cause, priority).
        artifacts: Preloaded ML models (LightGBM, etc.) from app startup.
        city_state: Live city state (stations, load, active incidents).
                    Agents read AND mutate this.

    Yields:
        JSON strings matching the SSE envelope:
        {
          "step": str,          # "init"|"triage"|"spatial"|"logistics"|"supervisor"|"directive"|"complete"
          "status": str,        # "running"|"done"|"retrying"|"escalated"|"error"
          "message": str,       # Human-readable label for UI
          "state": dict | null  # Serialized PlanState or null for init
        }

    Raises:
        Exception: Any unhandled exception is yielded as an error event,
                   then re-raised so FastAPI logs the full traceback.
    """
    settings = get_settings()
    state = PlanState(incident=incident)

    try:
        # ─────────────────────────────────────────────────────────────────
        # Init
        # ─────────────────────────────────────────────────────────────────
        yield json.dumps({
            "step": "init",
            "status": "done",
            "message": "Incident received, initializing plan...",
            "state": None,
        })
        await asyncio.sleep(0)

        # ─────────────────────────────────────────────────────────────────
        # Triage (outside loop — runs only once)
        # ─────────────────────────────────────────────────────────────────
        state = await _run_triage(state, artifacts)
        yield _make_event("triage", "done", "Severity assessment complete", state)
        await asyncio.sleep(0)

        # ─────────────────────────────────────────────────────────────────
        # Supervisor loop (wraps Spatial + Logistics only)
        # ─────────────────────────────────────────────────────────────────
        while True:
            state = await _run_spatial(state, settings)
            yield _make_event("spatial", "done", "Route diversion computed", state)
            await asyncio.sleep(0)

            state = await _run_logistics(state, settings,artifacts,city_state)
            yield _make_event("logistics", "done", "Resource allocation computed", state)
            await asyncio.sleep(0)

            state, should_break = await _run_supervisor(state,settings)
            msg = _supervisor_message(state, should_break)
            yield _make_event("supervisor", "done" if should_break else "retrying", msg, state)
            await asyncio.sleep(0)

            if should_break:
                break

            # Yield status before next iteration
            next_radius = state.spatial.current_buffer_radius_m if state.spatial else 800.0
            yield _make_event(
                "spatial",
                "running",
                f"Expanding buffer to {next_radius}m, re-calculating...",
                None,
            )
            await asyncio.sleep(0)

        # ─────────────────────────────────────────────────────────────────
        # Check escalation
        # ─────────────────────────────────────────────────────────────────
        if state.supervisor and state.supervisor.should_escalate:
            yield _make_event(
                "complete",
                "escalated",
                f"Escalated: {state.supervisor.escalation_reason}",
                state,
            )
            return

        # ─────────────────────────────────────────────────────────────────
        # Directive generation (post-loop)
        # ─────────────────────────────────────────────────────────────────
        state = await _run_directive(state, settings)
        yield _make_event("directive", "done", "Crisis communications generated", state)
        await asyncio.sleep(0)

        # ─────────────────────────────────────────────────────────────────
        # Commit to city state and finalize
        # ─────────────────────────────────────────────────────────────────
        _commit_plan_to_city_state(state, city_state)
        yield _make_event("complete", "done", "Plan complete and committed", state)

    except Exception as err:
        logger.exception(f"Pipeline error: {err}")
        yield json.dumps({
            "step": "error",
            "status": "error",
            "message": str(err),
            "state": None,
        })
        raise


# ═════════════════════════════════════════════════════════════════════════
# HELPERS (extracted to keep main generator under 20 lines)
# ═════════════════════════════════════════════════════════════════════════


def _make_event(step: str, status: str, message: str, state: PlanState | None) -> str:
    """Construct and serialize a single SSE event."""
    return json.dumps({
        "step": step,
        "status": status,
        "message": message,
        "state": json.loads(state.model_dump_json()) if state else None,
    })


def _supervisor_message(state: PlanState, should_break: bool) -> str:
    """Generate human-readable supervisor message."""
    if should_break:
        if state.supervisor and not state.supervisor.should_escalate:
            return "Plan feasible and approved."
        return "Plan escalated (max retries reached)."
    retry_num = state.supervisor.retry_count if state.supervisor else 0
    return f"Retry {retry_num + 1}: expanding buffer radius..."


async def _run_triage(state: PlanState, artifacts: "ModelArtifacts") -> PlanState:
    """Run Triage agent on thread pool (blocking LightGBM call)."""
    agent = TriageAgent(artifacts)
    result = await asyncio.to_thread(agent.run, state.incident)
    return state.advance(triage=result, stage="triage")


async def _run_spatial(state: PlanState, settings: "Settings") -> PlanState:
    """
    Run Spatial agent.

    NOTE: SpatialAgent.run() is itself `async def` (it does its own
    internal offloading of blocking NetworkX calls where needed), so
    we `await` it directly here instead of wrapping it in
    `asyncio.to_thread()`. Passing an async function to
    `asyncio.to_thread()` does NOT execute it — it just constructs
    and immediately returns an un-awaited coroutine object, which
    then fails JSON serialization downstream ("Unable to serialize
    unknown type: <class 'coroutine'>").
    """
    agent = SpatialAgent(settings)
    radius = state.spatial.current_buffer_radius_m if state.spatial else 800.0
    result = await agent.run(state.incident, radius)
    return state.advance(spatial=result, stage="spatial")


async def _run_logistics(state: PlanState, settings: "Settings", artifacts: "ModelArtifacts", city_state: "CityState") -> PlanState:
    """
    Run Logistics agent.

    NOTE: same async/await fix as _run_spatial — only wrap in
    asyncio.to_thread() if LogisticsAgent.run() is a plain blocking
    `def`. If it's `async def`, await it directly (as below).
    If your LogisticsAgent.run() is actually synchronous (wraps a
    blocking OR-Tools solver call with no internal awaits), revert
    this specific line to:
        result = await asyncio.to_thread(agent.run, state.triage, state.incident, state.spatial)
    """
    agent = LogisticsAgent(settings, artifacts.station_data,city_state)
    result = await agent.run(
        state.triage,
        state.incident,
    )
    return state.advance(logistics=result, stage="logistics")


async def _run_supervisor(
    state: PlanState,
    settings: "Settings",
) -> tuple[PlanState, bool]:
    """
    Run Supervisor check and return (updated_state, should_break).

    should_break=True if feasible or escalated (no more retries).

    NOTE: same async/await fix — if SupervisorAgent.check_and_adapt()
    is `async def`, await it directly. If it's a plain blocking `def`,
    keep it wrapped in asyncio.to_thread() instead.
    """
    agent = SupervisorAgent(settings)
    state = await agent.check_and_adapt(state)
    should_break = (
        state.supervisor.should_escalate
        or (state.logistics is not None and state.logistics.feasible)
    )
    return state, should_break


async def _run_directive(state: PlanState, settings: "Settings") -> PlanState:
    """
    ...
    """
    # Generate text outputs (tweet, SMS, dispatch script — spoken + written)
    outputs = generate_directive(state)
    dispatch_script_spoken = outputs["dispatch_script_spoken"]

    # Synthesize the SPOKEN script to audio (no raw coordinates in audio)
    audio_dir_path = Path(settings.audio_dir)
    if not audio_dir_path.is_absolute():
        audio_dir_path = Path(__file__).resolve().parent.parent.parent / audio_dir_path
    filename = await synthesize_dispatch_audio(dispatch_script_spoken, str(audio_dir_path))
    audio_url = f"/audio/{filename}"

    # Build DirectiveOutput and attach to state
    from app.core.state import DirectiveOutput
    directive = DirectiveOutput(
        tweet=outputs["tweet"],
        sms=outputs["sms"],
        dispatch_script=outputs["dispatch_script_written"],
        dispatch_audio_url=audio_url,
    )

    return state.advance(directive=directive, stage="complete")


def _commit_plan_to_city_state(state: PlanState, city_state: CityState) -> None:
    """
    Mutate city_state to reflect the completed plan.

    Decrements station availability, adds incident to active list,
    updates corridor load forecasts.
    """
    if not state.logistics or not state.logistics.feasible:
        logger.warning("Refusing to commit infeasible plan to city_state.")
        return

    # Decrement station availability
    for station_id, officer_count in state.logistics.assignments.items():
        if hasattr(city_state, "stations") and station_id in city_state.stations:
            city_state.stations[station_id]["available"] = max(
    0, city_state.stations[station_id]["available"] - officer_count
)

    # Add to active incidents
    if hasattr(city_state, "active_incidents"):
        city_state.active_incidents[state.plan_id] = {
            "incident": state.incident,
            "plan": state.logistics.assignments,
        }

    logger.info(f"Plan {state.plan_id} committed to city_state.")