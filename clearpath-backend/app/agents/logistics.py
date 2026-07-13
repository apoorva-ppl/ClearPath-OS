import asyncio
import math
import pandas as pd
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.state import CityState, IncidentInput, LogisticsOutput, TriageOutput

class LogisticsError(RuntimeError):
    pass

#represents a police station(id , location, capacity)
class PoliceStation(BaseModel):
    model_config = ConfigDict(frozen=True)

    station_id: str
    name: str
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
    max_capacity: int = Field(gt=0)

#converts station dataset->policeStation objects
def _get_real_stations(station_data: pd.DataFrame) -> list[PoliceStation]:

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
#calculates dist between incident n police stations
def _haversine_km(
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    lat_a, lng_a = a
    lat_b, lng_b = b
    earth_radius_km = 6_371

    lat_a_rad = math.radians(lat_a)
    lat_b_rad = math.radians(lat_b)
    delta_lat = math.radians(lat_b - lat_a)
    delta_lng = math.radians(lng_b - lng_a)
    #haversine formula
    a_val = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a_rad) * math.cos(
        lat_b_rad
    ) * math.sin(delta_lng / 2) ** 2
    c_val = 2 * math.atan2(math.sqrt(a_val), math.sqrt(1 - a_val))

    return earth_radius_km * c_val

#removes too far stations 
def _filter_eligible_stations(
    stations: list[PoliceStation],
    incident: tuple[float, float],
    max_distance_km: float,
) -> list[tuple[PoliceStation, float]]:
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

#low severity -> 2 officer , high severity -> 10 officers
def _get_officer_demand(
    severity_tier: str,
    settings: Any,
) -> int:
    demand_map = {
        "Low": settings.manpower.low.officers,
        "Medium": settings.manpower.medium.officers,
        "High": settings.manpower.high.officers,
    }
    if severity_tier not in demand_map:
        raise ValueError(f"Unknown severity tier: {severity_tier}")
    return demand_map[severity_tier]

#ILP-> finds best resource allocation while satisfying all constraints
def _build_and_solve_ilp(
    eligible: list[tuple[PoliceStation, float]],
    demand: int,
    settings: Any,
    live_availability: dict[str, int],
) -> tuple[dict[str, int], str]:
   
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

    # Objective:distance x officer (use nearest stations possible)
    objective = solver.Objective()
    for station, dist_km in eligible:
        objective.SetCoefficient(x[station.station_id], dist_km)
    objective.SetMinimization()

    # Constraint (if demand =10 , officer =10)
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

#ILP fails -> dont crash , just greedily dispactch the nearest avail stations
def _greedy_fallback(
    eligible: list[tuple[PoliceStation, float]],
    demand: int,
) -> dict[str, int]:
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

#main function
class LogisticsAgent:

    def __init__(self, settings: Any, station_data: pd.DataFrame, city_state:"CityState") -> None:
   
        self.settings = settings
        self.station_data = station_data
        self.city_state = city_state

    async def run(
        self,
        triage: TriageOutput,
        incident: IncidentInput,
    ) -> LogisticsOutput:
        
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
#factory function , creates ready to use logisticAgent
def create_logistics_agent(settings: Any | None = None) -> LogisticsAgent:
   
    if settings is None:
        settings = get_settings()
    return LogisticsAgent(settings)