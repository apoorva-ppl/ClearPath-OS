"""
optimize_resources.py  —  Stage 5.

IN : - list of active incidents, each with predicted severity + coords
       [{"id","lat","lng","severity","requires_road_closure"}, ...]
     - station roster (synthesised from the clean data's police_station column)
       [{"station","lat","lng","capacity"}, ...]
OUT: {"assignments":[{incident_id, station, officers, distance_km}],
      "barricades":{incident_id: count},
      "uncovered":[incident_id,...], "total_distance_km": float, "feasible": bool}

Task type
---------
CONSTRAINED OPTIMISATION, not ML. Police stations are SUPPLY nodes (officer
capacity); incidents are DEMAND nodes (officers needed, by severity). Edge cost
= station->incident distance. We minimise total officer-distance subject to
capacity, using OR-Tools min-cost flow. A greedy nearest-station fallback runs
if OR-Tools is unavailable or the graph is degenerate — it gives near-identical
output for demo scale.

We optimise rather than imitate historical deployments on purpose: there's no
ground truth that past gut-feel placements were optimal, and the goal is to
improve on them.

Run (self-test): python -m src.optimize_resources
"""
from __future__ import annotations

from .utils import load_config, haversine_km, log


def _demand(sev: str, cfg: dict) -> int:
    return cfg["resources"]["officers_per_severity"].get(sev, 1)


def _barricades(inc: dict, cfg: dict) -> int:
    r = cfg["resources"]
    base = r["barricades_per_severity"].get(inc["severity"], 0)
    if inc.get("requires_road_closure"):
        base += r["closure_barricade_bonus"]
    return base


def allocate(incidents: list[dict], stations: list[dict],
             cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    max_km = cfg["resources"]["max_assign_distance_km"]

    # barricades are a pure per-incident rule
    barricades = {inc["id"]: _barricades(inc, cfg) for inc in incidents}

    try:
        result = _solve_min_cost_flow(incidents, stations, cfg, max_km)
        method = "or-tools-min-cost-flow"
    except Exception as e:                      # noqa: BLE001 - fallback is the point
        log(f"optimize: OR-Tools path failed ({e}); using greedy fallback")
        result = _solve_greedy(incidents, stations, cfg, max_km)
        method = "greedy-fallback"

    result["barricades"] = barricades
    result["method"] = method
    result["feasible"] = len(result["uncovered"]) == 0
    return result


# ---------------------------------------------------------------- OR-Tools ----
def _solve_min_cost_flow(incidents, stations, cfg, max_km) -> dict:
    from ortools.graph.python import min_cost_flow

    mcf = min_cost_flow.SimpleMinCostFlow()
    # node ids: 0..S-1 stations, S..S+I-1 incidents, plus source & sink
    S, I = len(stations), len(incidents)
    SRC, SINK = S + I, S + I + 1

    demands = [_demand(inc["severity"], cfg) for inc in incidents]
    total_demand = sum(demands)

    # source -> station (capacity = officers available, cost 0)
    for s, st in enumerate(stations):
        mcf.add_arc_with_capacity_and_unit_cost(SRC, s, st["capacity"], 0)

    # station -> incident (capacity = demand, cost = distance in metres as int)
    arc_index = {}
    for s, st in enumerate(stations):
        for i, inc in enumerate(incidents):
            d = haversine_km(st["lat"], st["lng"], inc["lat"], inc["lng"])
            if d > max_km:
                continue
            cost = int(d * 1000)            # metres -> integer cost
            a = mcf.add_arc_with_capacity_and_unit_cost(s, S + i, demands[i], cost)
            arc_index[(s, i)] = a

    # incident -> sink (capacity = demand, cost 0)
    for i in range(I):
        mcf.add_arc_with_capacity_and_unit_cost(S + i, SINK, demands[i], 0)

    # we want to push as much demand as the network allows -> set supply at SRC
    mcf.set_node_supply(SRC, total_demand)
    mcf.set_node_supply(SINK, -total_demand)

    status = mcf.solve_max_flow_with_min_cost() if hasattr(
        mcf, "solve_max_flow_with_min_cost") else mcf.solve()

    assignments, served = [], {i: 0 for i in range(I)}
    for (s, i), a in arc_index.items():
        f = mcf.flow(a)
        if f > 0:
            served[i] += f
            assignments.append({
                "incident_id": incidents[i]["id"],
                "station": stations[s]["station"],
                "officers": int(f),
                "distance_km": round(
                    haversine_km(stations[s]["lat"], stations[s]["lng"],
                                 incidents[i]["lat"], incidents[i]["lng"]), 2),
            })

    uncovered = [incidents[i]["id"] for i in range(I) if served[i] < demands[i]]
    total_km = sum(a["distance_km"] * a["officers"] for a in assignments)
    return {"assignments": assignments, "uncovered": uncovered,
            "total_distance_km": round(total_km, 2)}


# ----------------------------------------------------------------- greedy -----
def _solve_greedy(incidents, stations, cfg, max_km) -> dict:
    cap = {st["station"]: st["capacity"] for st in stations}
    assignments, uncovered = [], []
    # serve highest-demand incidents first
    order = sorted(range(len(incidents)),
                   key=lambda i: -_demand(incidents[i]["severity"], cfg))
    for i in order:
        inc = incidents[i]
        need = _demand(inc["severity"], cfg)
        # nearest stations with capacity
        ranked = sorted(
            stations,
            key=lambda st: haversine_km(st["lat"], st["lng"], inc["lat"], inc["lng"]),
        )
        for st in ranked:
            if need <= 0:
                break
            d = haversine_km(st["lat"], st["lng"], inc["lat"], inc["lng"])
            if d > max_km or cap[st["station"]] <= 0:
                continue
            give = min(need, cap[st["station"]])
            cap[st["station"]] -= give
            need -= give
            assignments.append({
                "incident_id": inc["id"], "station": st["station"],
                "officers": int(give), "distance_km": round(d, 2),
            })
        if need > 0:
            uncovered.append(inc["id"])
    total_km = sum(a["distance_km"] * a["officers"] for a in assignments)
    return {"assignments": assignments, "uncovered": uncovered,
            "total_distance_km": round(total_km, 2)}


if __name__ == "__main__":
    # tiny self-test
    incs = [
        {"id": "A", "lat": 12.97, "lng": 77.59, "severity": "High",
         "requires_road_closure": True},
        {"id": "B", "lat": 13.03, "lng": 77.51, "severity": "Medium",
         "requires_road_closure": False},
    ]
    stns = [
        {"station": "Central", "lat": 12.98, "lng": 77.60, "capacity": 12},
        {"station": "Peenya", "lat": 13.03, "lng": 77.52, "capacity": 12},
    ]
    from pprint import pprint
    pprint(allocate(incs, stns))
