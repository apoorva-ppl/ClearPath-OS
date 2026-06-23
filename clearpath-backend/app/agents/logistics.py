# OR-Tools ILP Optimization
# app/agents/logistics.py
"""
Agent 3: OR-Tools ILP Resource Optimization.

Two-tier dispatch strategy:
  1. ILP solver: minimizes distance-weighted officer deployment.
  2. Greedy fallback: used when ILP is infeasible.

Scenario showing why ILP beats greedy:
  - Two simultaneous incidents 500 m apart in Zone A.
  - Three stations: Station A (capacity 10, 1 km away),
    Station B (capacity 5, 5 km away), Station C (capacity 5, 20 km away).
  - Demand per incident: 6 officers.

  Greedy (incident-by-incident):
    Incident 1: Assign 6 from Station A (now has 4 left).
    Incident 2: Assign 4 from Station A, 2 from Station B.
    Total distance cost: 6*1 + 4*1 + 2*5 = 16 km-officers.

  ILP (simultaneous):
    Sees both demands at once. Assigns:
    Incident 1: 5 from Station A, 1 from Station B.
    Incident 2: 5 from Station A, 1 from Station B.
    Total distance cost: 5*1 + 1*5 + 5*1 + 1*5 = 16 km-officers.
    Same cost, but ILP guarantees optimality across all constraints,
    while greedy is locally myopic per incident.

When multiple incidents are active: ILP sees the full problem and
allocates officers globally optimal; greedy processes serially and
can starve later incidents.
"""

import asyncio
import math
import pandas as pd
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.state import CityState, IncidentInput, LogisticsOutput, TriageOutput


# ════════════════════════════════════════════════════════════════
# CUSTOM EXCEPTION
# ════════════════════════════════════════════════════════════════


class LogisticsError(RuntimeError):
    """
    Raised when no eligible stations exist or solver initialization fails.

    Indicates either resource constraints are unachievable or the
    optimization environment is misconfigured.
    """

    pass


# ════════════════════════════════════════════════════════════════
# STATION DATA MODEL
# ════════════════════════════════════════════════════════════════


class PoliceStation(BaseModel):
    """
    Typed container for police station metadata.

    Using a Pydantic model (not a raw dict) catches schema drift at
    parse time, preventing subtle bugs in the ILP loop.

    Attributes:
        station_id: Unique identifier (e.g., "ps_cubbon_park").
        name: Human-readable station name.
        lat: Latitude in WGS-84.
        lng: Longitude in WGS-84.
        max_capacity: Maximum deployable officers from this station.
    """

    model_config = ConfigDict(frozen=True)

    station_id: str
    name: str
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
    max_capacity: int = Field(gt=0)


# ════════════════════════════════════════════════════════════════
# REAL STATION REGISTRY
# ════════════════════════════════════════════════════════════════

def _get_real_stations(station_data: pd.DataFrame) -> list[PoliceStation]:
    """
    Build PoliceStation objects from the real 54-station dataset.

    Replaces the old hardcoded 4-station mock. station_data is the
    DataFrame loaded from stations.csv (columns: station_id, lat,
    lng, capacity), already attached to ModelArtifacts at startup.

    Args:
        station_data: DataFrame with columns station_id, lat, lng, capacity.

    Returns:
        List of PoliceStation objects, one per row.
    """
    return [
        PoliceStation(
            station_id=row["station_id"],
            name=f"{row['station_id']} PS",
            lat=row["lat"],
            lng=row["lng"],
            max_capacity=int(row["capacity"]),
        )
        for _, row in station_data.iterrows()
    ]


# ════════════════════════════════════════════════════════════════
# HAVERSINE DISTANCE (local helper)
# ════════════════════════════════════════════════════════════════


def _haversine_km(
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    """
    Calculate great-circle distance in kilometres between two WGS-84 points.

    Args:
        a: (latitude, longitude) in degrees.
        b: (latitude, longitude) in degrees.

    Returns:
        Distance in kilometres.
    """
    lat_a, lng_a = a
    lat_b, lng_b = b
    earth_radius_km = 6_371

    lat_a_rad = math.radians(lat_a)
    lat_b_rad = math.radians(lat_b)
    delta_lat = math.radians(lat_b - lat_a)
    delta_lng = math.radians(lng_b - lng_a)

    a_val = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a_rad) * math.cos(
        lat_b_rad
    ) * math.sin(delta_lng / 2) ** 2
    c_val = 2 * math.atan2(math.sqrt(a_val), math.sqrt(1 - a_val))

    return earth_radius_km * c_val


# ════════════════════════════════════════════════════════════════
# STATION FILTERING
# ════════════════════════════════════════════════════════════════


def _filter_eligible_stations(
    stations: list[PoliceStation],
    incident: tuple[float, float],
    max_distance_km: float,
) -> list[tuple[PoliceStation, float]]:
    """
    Filter stations by maximum dispatch distance.

    Computes Haversine distance from incident to each station and
    returns only those within max_distance_km, paired with their
    distance for cost computation.

    Including far stations in the ILP allows technically feasible
    plans where officers arrive after the golden hour has closed —
    a safety liability. Hard filtering ensures operational realism.

    Args:
        stations: List of PoliceStation objects.
        incident: (lat, lng) of incident center.
        max_distance_km: Maximum eligible dispatch distance.

    Returns:
        List of (station, distance_km) tuples for eligible stations.

    Raises:
        LogisticsError: If no eligible stations exist within the
            maximum distance.
    """
    eligible = []
    for station in stations:
        station_coord = (station.lat, station.lng)
        dist_km = _haversine_km(incident, station_coord)
        if dist_km <= max_distance_km:
            eligible.append((station, dist_km))

    if not eligible:
        raise LogisticsError(
            f"No eligible stations within {max_distance_km} km of incident "
            f"at ({incident[0]}, {incident[1]})"
        )

    return eligible


# ════════════════════════════════════════════════════════════════
# DEMAND LOOKUP
# ════════════════════════════════════════════════════════════════


def _get_officer_demand(
    severity_tier: str,
    settings: Any,
) -> int:
    """
    Map severity tier to required officer count from config.

    Operational commanders adjust these values seasonally (e.g., festivals).
    Config-driven demands prevent coupling between policy and code,
    eliminating the need for code deployments on every tactical adjustment.

    Args:
        severity_tier: One of "Low", "Medium", "High".
        settings: Configuration object.

    Returns:
        Number of officers required for this severity level.

    Raises:
        ValueError: If severity_tier is unknown.
    """
    demand_map = {
        "Low": settings.manpower.low.officers,
        "Medium": settings.manpower.medium.officers,
        "High": settings.manpower.high.officers,
    }
    if severity_tier not in demand_map:
        raise ValueError(f"Unknown severity tier: {severity_tier}")
    return demand_map[severity_tier]


# ════════════════════════════════════════════════════════════════
# ILP SOLVER
# ════════════════════════════════════════════════════════════════


def _build_and_solve_ilp(
    eligible: list[tuple[PoliceStation, float]],
    demand: int,
    settings: Any,
    live_availability: dict[str, int],
) -> tuple[dict[str, int], str]:
    """
    Formulate and solve the officer deployment optimization problem.

    Objective: Minimize sum(distance_km * officers_deployed).

    Why distance-weighted, not just total distance:
      - Assigning N officers from a far station incurs N times the
        cumulative travel cost. Minimizing distance*officers balances
        load across closer and farther stations optimally.

    Constraints:
      C1: Exact demand match (sum of deployed officers == demand).
          Not >= because over-deployment pulls officers from other
          active incidents, reducing system resilience.
      C2: Per-station capacity (x[sid] <= max_capacity).
          Defensive; already encoded in IntVar bounds.
      C3: Stations beyond max_dispatch_distance are excluded.
          Also defensive; already filtered by _filter_eligible_stations.

    Args:
        eligible: List of (station, distance_km) tuples.
        demand: Required officer count.
        settings: Configuration object.

    Returns:
        Tuple of (assignments_dict, status_string).
        assignments_dict maps station_id → officer_count.
        status_string is one of "OPTIMAL", "FEASIBLE", "INFEASIBLE".

    Raises:
        LogisticsError: If solver initialization fails (SCIP unavailable).
    """
    try:
        from ortools.linear_solver import pywraplp
    except ImportError:
        raise LogisticsError(
            "OR-Tools not installed. Install with: pip install ortools"
        )

    solver = pywraplp.Solver.CreateSolver("SCIP")
    if not solver:
        raise LogisticsError(
            "SCIP solver unavailable. Check OR-Tools installation."
        )

    # Decision variables: officers deployed from each station
    x = {}
    for station, _ in eligible:
        upper_bound = live_availability.get(station.station_id, 0)
        x[station.station_id] = solver.IntVar(
            0, upper_bound, station.station_id
        )

    # Objective: minimize distance-weighted officer deployment
    objective = solver.Objective()
    for station, dist_km in eligible:
        objective.SetCoefficient(x[station.station_id], dist_km)
    objective.SetMinimization()

    # Constraint C1: Exact demand match
    constraint_demand = solver.Constraint(demand, demand, "demand")
    for station_id in x:
        constraint_demand.SetCoefficient(x[station_id], 1)

    # Solve
    status = solver.Solve()

    # Map status to string
    status_map = {
        pywraplp.Solver.OPTIMAL: "OPTIMAL",
        pywraplp.Solver.FEASIBLE: "FEASIBLE",
    }
    status_string = status_map.get(status, "INFEASIBLE")

    # Extract assignments if feasible
    assignments = {}
    if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        for station_id, var in x.items():
            value = int(var.solution_value())
            if value > 0:
                assignments[station_id] = value

    return assignments, status_string


# ════════════════════════════════════════════════════════════════
# GREEDY FALLBACK
# ════════════════════════════════════════════════════════════════


def _greedy_fallback(
    eligible: list[tuple[PoliceStation, float]],
    demand: int,
) -> dict[str, int]:
    """
    Fallback greedy allocation when ILP is infeasible.

    Sorts stations by distance and fills demand greedily. May not
    satisfy full demand if total capacity is insufficient.

    Exposed as a named function (not inline logic) so the supervisor
    can inspect which allocation path was taken from the stack trace.

    Args:
        eligible: List of (station, distance_km) tuples.
        demand: Required officer count.

    Returns:
        Partial assignment dict (may not satisfy full demand).
    """
    # Sort by distance (nearest first)
    sorted_eligible = sorted(eligible, key=lambda x: x[1])

    assignments = {}
    remaining = demand
    for station, _ in sorted_eligible:
        if remaining <= 0:
            break
        alloc = min(remaining, station.max_capacity)
        assignments[station.station_id] = alloc
        remaining -= alloc

    return assignments


# ════════════════════════════════════════════════════════════════
# LOGISTICS AGENT
# ════════════════════════════════════════════════════════════════


class LogisticsAgent:
    """
    OR-Tools ILP resource allocation agent.

    Single responsibility: take triage results and incident location,
    produce an officer and barricade deployment plan. Does not route,
    classify, or coordinate with other agents — only allocates resources.

    Attributes:
        settings: Loaded configuration object.
    """

    def __init__(self, settings: Any, station_data: pd.DataFrame, city_state:"CityState") -> None:
        """
        Initialize LogisticsAgent with configuration and real station data.
        Args:
        settings: app.core.config.Settings object.
        station_data: DataFrame of all 54 real police stations.
    """
        self.settings = settings
        self.station_data = station_data
        self.city_state = city_state

    async def run(
        self,
        triage: TriageOutput,
        incident: IncidentInput,
    ) -> LogisticsOutput:
        """
        Compute optimal officer and barricade deployment.

        Orchestration:
          1. Load mock station registry.
          2. Filter eligible stations by max dispatch distance.
          3. Look up officer demand by severity tier.
          4. Call blocking ILP solver on thread pool.
          5. If OPTIMAL or FEASIBLE → use ILP result.
          6. If INFEASIBLE → try greedy fallback.
          7. Return LogisticsOutput with assignments, total counts,
             feasibility flag, and solver status.

        Deployment Outcomes:
          - OPTIMAL/FEASIBLE: assignments dict populated, feasible=True.
          - Greedy fallback: assignments dict may be partial, feasible=False
            if fallback demand is unmet.
          - Catastrophic failure: empty assignments, feasible=False,
            status="INFEASIBLE".

        Args:
            triage: Severity tier and closure probability from triage agent.
            incident: Raw incident with lat/lng.

        Returns:
            LogisticsOutput with dispatch plan, officer/barricade counts,
            feasibility, and solver status for audit.

        Raises:
            LogisticsError: If no eligible stations exist or solver fails.
            ValueError: If severity_tier is unknown.
        """
        # Step 1: Load stations
        stations = _get_real_stations(self.station_data)

        # Step 2: Filter by distance
        incident_coord = (incident.lat, incident.lng)
        max_dist_km = self.settings.logistics.max_dispatch_distance_km
        try:
            eligible = _filter_eligible_stations(
                stations, incident_coord, max_dist_km
            )
        except LogisticsError as e:
            # No eligible stations — return infeasible
            return LogisticsOutput(
                assignments={},
                total_officers=0,
                total_barricades=0,
                feasible=False,
                solver_status=f"INFEASIBLE: {str(e)}",
            )

        # Step 3: Lookup demand
        demand = _get_officer_demand(triage.severity_tier, self.settings)

        # Step 4: Solve ILP on thread pool
        live_availability = {
    sid: data["available"] for sid, data in self.city_state.stations.items()
}
        ilp_assignments, ilp_status = await asyncio.to_thread(
            _build_and_solve_ilp,
            eligible,
            demand,
            self.settings,
            live_availability,
        )

        # Step 5–6: Use ILP or fallback
        if ilp_status in ("OPTIMAL", "FEASIBLE"):
            assignments = ilp_assignments
            feasible = ilp_status == "OPTIMAL"
            solver_status = ilp_status
        else:
            # Try greedy fallback
            assignments = _greedy_fallback(eligible, demand)
            feasible = sum(assignments.values()) == demand
            solver_status = "FALLBACK"

        # Step 7: Compute total officers
        total_officers = sum(assignments.values())

        # Compute barricades from manpower matrix
        manpower_tier = {
            "Low": self.settings.manpower.low,
            "Medium": self.settings.manpower.medium,
            "High": self.settings.manpower.high,
        }
        manpower = manpower_tier.get(
            triage.severity_tier,
            self.settings.manpower.low,
        )
        total_barricades = manpower.barricades

        return LogisticsOutput(
            assignments=assignments,
            total_officers=total_officers,
            total_barricades=total_barricades,
            feasible=feasible,
            solver_status=solver_status,
        )


# ════════════════════════════════════════════════════════════════
# MODULE FACTORY
# ════════════════════════════════════════════════════════════════


def create_logistics_agent(settings: Any | None = None) -> LogisticsAgent:
    """
    Factory function: construct a fully-initialized LogisticsAgent.

    Args:
        settings: Configuration object. Defaults to get_settings() if None.

    Returns:
        Ready-to-use LogisticsAgent instance.
    """
    if settings is None:
        settings = get_settings()
    return LogisticsAgent(settings)