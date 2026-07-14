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

#main function(recieves incident,model artifacts, citystate)
async def stream_incident_plan(
    incident: IncidentInput,
    artifacts: "ModelArtifacts",
    city_state: CityState,
) -> AsyncGenerator[str, None]:
    settings = get_settings()
    state = PlanState(incident=incident)

    try:
        # We use an AsyncGenerator with yield so the frontend receives live progress updates instead of waiting for the entire workflow to finish
        yield json.dumps({
            "step": "init",
            "status": "done",
            "message": "Incident received, initializing plan...",
            "state": None,
        })
        await asyncio.sleep(0)

        # triage(instead of changing state , create new state)
        state = await _run_triage(state, artifacts)
        yield _make_event("triage", "done", "Severity assessment complete", state)
        await asyncio.sleep(0)

        # supervisor loop
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

        # check escalation
        if state.supervisor and state.supervisor.should_escalate:
            yield _make_event(
                "complete",
                "escalated",
                f"Escalated: {state.supervisor.escalation_reason}",
                state,
            )
            return

        # directive generation
        state = await _run_directive(state, settings)
        yield _make_event("directive", "done", "Crisis communications generated", state)
        await asyncio.sleep(0)

        # commit to city state n finalise
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

#helper functions

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
    agent = SpatialAgent(settings)
    radius = state.spatial.current_buffer_radius_m if state.spatial else 800.0
    result = await agent.run(state.incident, radius)
    return state.advance(spatial=result, stage="spatial")


async def _run_logistics(state: PlanState, settings: "Settings", artifacts: "ModelArtifacts", city_state: "CityState") -> PlanState:
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