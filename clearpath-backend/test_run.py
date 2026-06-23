#!/usr/bin/env python3
"""
Integration Test: Linear Pipeline Execution.

This script mirrors the exact flow that app/core/generator.py will execute
asynchronously in the FastAPI SSE handler. Here we run it synchronously
(wrapped in asyncio.run()) to verify:

  1. PlanState contracts between agents (type safety, immutability).
  2. OR-Tools and NetworkX math (no solver crashes, valid paths).
  3. Supervisor decision logic (feasibility checks, expansion triggers).

The output is a readable trace showing each stage, facilitating debugging
before the full async pipeline goes live.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path so imports work from any working directory
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings
from app.core.state import IncidentInput, PlanState
from app.agents.triage import create_triage_agent
from app.agents.spatial import create_spatial_agent
from app.agents.logistics import create_logistics_agent
from app.agents.supervisor import create_supervisor_agent


# ════════════════════════════════════════════════════════════════
# MOCK INCIDENT
# ════════════════════════════════════════════════════════════════


def create_mock_incident() -> IncidentInput:
    """Create a realistic test incident in central Bengaluru."""
    return IncidentInput(
        lat=12.9716,
        lng=77.5946,
        cause="Accident",
        priority="high",
    )


# ════════════════════════════════════════════════════════════════
# PIPELINE ORCHESTRATION
# ════════════════════════════════════════════════════════════════


async def run_pipeline() -> None:
    """
    Execute the full 4-agent pipeline on a mock incident.

    This mirrors the structure of app/core/generator.py:
      1. Initialize PlanState from incident.
      2. Run Triage agent → update PlanState.
      3. Run Spatial agent → update PlanState.
      4. Run Logistics agent → update PlanState.
      5. Run Supervisor agent → check feasibility.
      6. If infeasible and expandable, loop back to step 3 with expanded
         buffer radius (simulated via supervisor's stage signal).
    """

    print("\n" + "=" * 70)
    print("CLEARPATH INTEGRATION TEST: 4-AGENT PIPELINE")
    print("=" * 70 + "\n")

    # Load configuration once (cached)
    settings = get_settings()
    print(f"✓ Configuration loaded (grid_resolution: {settings.spatial.grid_resolution_m}m)")

    # Create agent instances
    triage_agent = create_triage_agent()
    spatial_agent = create_spatial_agent(settings)
    logistics_agent = create_logistics_agent(settings)
    supervisor_agent = create_supervisor_agent(settings)
    print("✓ All 4 agents instantiated\n")

    # Create mock incident
    incident = create_mock_incident()
    print("--- MOCK INCIDENT ---")
    print(f"Location: ({incident.lat:.4f}, {incident.lng:.4f})")
    print(f"Cause: {incident.cause}")
    print(f"Priority: {incident.priority}\n")

    # Initialize PlanState (immutable from here on; only .advance() creates new instances)
    plan = PlanState(incident=incident)
    print(f"Plan ID: {plan.plan_id}")
    print(f"Initial stage: {plan.stage}\n")

    # ════════════════════════════════════════════════════════════════
    # STAGE 1: TRIAGE
    # ════════════════════════════════════════════════════════════════

    print("--- STAGE 1: TRIAGE ---")
    triage_result = await triage_agent.run(incident)
    plan = plan.advance(triage=triage_result, stage="triage")
    print(f"Severity Tier: {triage_result.severity_tier}")
    print(f"Closure Probability: {triage_result.closure_prob:.2%}")
    print(f"Predicted Duration: {triage_result.predicted_duration_minutes} min")
    print(f"Model Version: {triage_result.model_version}\n")

    # ════════════════════════════════════════════════════════════════
    # EXPANSION LOOP (Supervisor controls this via stage signals)
    # ════════════════════════════════════════════════════════════════

    expansion_cycle = 0
    max_cycles = settings.supervisor.max_expansion_attempts + 1

    while expansion_cycle < max_cycles:
        expansion_cycle += 1
        print(f"--- CYCLE {expansion_cycle} ---\n")

        # ────────────────────────────────────────────────────────────
        # STAGE 2: SPATIAL
        # ────────────────────────────────────────────────────────────

        print("  → STAGE 2: SPATIAL (NetworkX Pathfinding)")
        buffer_radius = plan.spatial.current_buffer_radius_m if plan.spatial else settings.spatial.base_buffer_radius_m
        spatial_result = await spatial_agent.run(incident, buffer_radius)
        plan = plan.advance(spatial=spatial_result, stage="spatial")

        baseline_len = len(spatial_result.baseline_path)
        diversion_len = len(spatial_result.diversion_path)
        print(f"    Baseline path waypoints: {baseline_len}")
        print(f"    Diversion path waypoints: {diversion_len}")
        print(f"    Buffer radius: {spatial_result.current_buffer_radius_m:.1f}m")
        print(f"    Nodes affected: {spatial_result.nodes_affected}\n")

        # ────────────────────────────────────────────────────────────
        # STAGE 3: LOGISTICS
        # ────────────────────────────────────────────────────────────

        print("  → STAGE 3: LOGISTICS (OR-Tools ILP)")
        logistics_result = await logistics_agent.run(triage_result, incident)
        plan = plan.advance(logistics=logistics_result, stage="logistics")

        print(f"    Solver Status: {logistics_result.solver_status}")
        print(f"    Feasible: {logistics_result.feasible}")
        print(f"    Total Officers: {logistics_result.total_officers}")
        print(f"    Total Barricades: {logistics_result.total_barricades}")
        print(f"    Assignments:")
        for station_id, count in logistics_result.assignments.items():
            print(f"      • {station_id}: {count} officers")
        print()

        # ────────────────────────────────────────────────────────────
        # STAGE 4: SUPERVISOR
        # ────────────────────────────────────────────────────────────

        print("  → STAGE 4: SUPERVISOR (Feasibility Check)")
        supervisor_result = await supervisor_agent.check_and_adapt(plan)
        print(f"    Decision: {'ESCALATE' if supervisor_result.supervisor.should_escalate else 'PROCEED'}")
        print(f"    Retry Count: {supervisor_result.supervisor.retry_count}")
        print(f"    Expansion Applied: {supervisor_result.supervisor.expansion_applied}")
        if supervisor_result.supervisor.escalation_reason:
            print(f"    Reason: {supervisor_result.supervisor.escalation_reason}")
        print(f"    Next Stage: {supervisor_result.stage}\n")

        # Update plan with supervisor's decision
        plan = supervisor_result

        # Check terminal conditions
        if plan.stage == "complete":
            print("✓ PIPELINE COMPLETE: Plan is feasible and approved.")
            print(f"  Final Stage: {plan.stage}")
            break
        elif plan.stage == "failed":
            print("✗ PIPELINE FAILED: Max expansion attempts reached, escalating to human commander.")
            print(f"  Final Stage: {plan.stage}")
            break
        elif plan.stage == "spatial":
            # Supervisor signalled re-expansion; loop continues
            print(f"→ Expanding buffer radius and retrying spatial + logistics...\n")
            continue

    # ════════════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ════════════════════════════════════════════════════════════════

    print("\n" + "=" * 70)
    print("FINAL PLAN STATE SNAPSHOT")
    print("=" * 70)
    print(f"Plan ID: {plan.plan_id}")
    print(f"Stage: {plan.stage}")
    print(f"Triage: {plan.triage.severity_tier if plan.triage else 'None'}")
    print(f"Spatial: {len(plan.spatial.diversion_path) if plan.spatial else 0} waypoints")
    print(f"Logistics: {plan.logistics.total_officers if plan.logistics else 0} officers")
    print(f"Supervisor: {'ESCALATED' if plan.supervisor and plan.supervisor.should_escalate else 'APPROVED'}")
    print("=" * 70 + "\n")


# ════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    try:
        asyncio.run(run_pipeline())
        print("✓ Test completed successfully.\n")
    except Exception as e:
        print(f"\n✗ Test failed with error:\n{type(e).__name__}: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)
