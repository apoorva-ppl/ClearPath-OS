"""
route_diversion.py  —  Stage 6.

IN : - incident coords (lat, lng) + a buffer radius (m)
     - a base road graph (built once from incident coordinates as a proxy grid)
OUT: {"affected_edges": [...], "buffer_radius_m": float,
      "diversion_path": [[lat,lng],...] | None,
      "baseline_path":  [[lat,lng],...] | None}

Task type
---------
GRAPH SHORTEST-PATH, not ML. We model the area as a NetworkX graph. When an
incident is logged we inflate the travel cost of every edge whose midpoint lies
within the buffer ("exclusion zone" / spatial buffer — a haversine radius test,
which is the same idea as a PostGIS ST_DWithin geofence, just in-process).
Dijkstra over the inflated graph yields a route that naturally bends around the
congested zone. Comparing it to the un-inflated shortest path shows the "ripple"
the incident causes.

The base graph here is synthesised by snapping incident points to a coarse grid
and connecting neighbouring cells. For a production system you would swap in an
OSMnx street graph for the city; the interface (build_graph / reroute) stays the
same. This keeps the 48h build dependency-free while remaining honest about the
upgrade path.

Run (self-test): python -m src.route_diversion
"""
from __future__ import annotations

import networkx as nx
import pandas as pd

from .utils import load_config, resolve, haversine_km, log


def _grid_key(lat: float, lng: float, cell_deg: float) -> tuple[int, int]:
    return (round(lat / cell_deg), round(lng / cell_deg))


def build_graph(cfg: dict | None = None) -> nx.Graph:
    """Build a reusable base road-proxy graph from incident coordinates.

    Nodes = occupied grid cells (lat/lng centroid). Edges connect 8-neighbour
    cells, weighted by great-circle distance (km). Loaded once and reused.
    """
    cfg = cfg or load_config()
    # ~400 m at Bengaluru's latitude is ~0.0036 deg; derive from config metres
    cell_deg = cfg["diversion"]["graph_grid_m"] / 111_000.0

    df = pd.read_parquet(resolve(cfg["paths"]["clean_parquet"]))
    cells: dict[tuple[int, int], tuple[float, float]] = {}
    for lat, lng in zip(df["latitude"], df["longitude"]):
        k = _grid_key(lat, lng, cell_deg)
        if k not in cells:
            cells[k] = (k[0] * cell_deg, k[1] * cell_deg)

    G = nx.Graph()
    for k, (clat, clng) in cells.items():
        G.add_node(k, lat=clat, lng=clng)

    # connect 8-neighbours
    for (gi, gj) in list(cells.keys()):
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                nb = (gi + di, gj + dj)
                if nb in cells and not G.has_edge((gi, gj), nb):
                    a, b = cells[(gi, gj)], cells[nb]
                    w = haversine_km(a[0], a[1], b[0], b[1])
                    G.add_edge((gi, gj), nb, weight=w, base_weight=w)

    log(f"diversion: base graph {G.number_of_nodes()} nodes / "
        f"{G.number_of_edges()} edges (grid {cfg['diversion']['graph_grid_m']}m)")
    return G


def _nearest_node(G: nx.Graph, lat: float, lng: float):
    return min(G.nodes,
               key=lambda n: haversine_km(G.nodes[n]["lat"], G.nodes[n]["lng"],
                                          lat, lng))


def _inflate(G: nx.Graph, lat: float, lng: float, radius_m: float,
             factor: float) -> list:
    """Multiply edge weight by `factor` for edges whose midpoint is in buffer."""
    affected = []
    r_km = radius_m / 1000.0
    for u, v, data in G.edges(data=True):
        mlat = (G.nodes[u]["lat"] + G.nodes[v]["lat"]) / 2
        mlng = (G.nodes[u]["lng"] + G.nodes[v]["lng"]) / 2
        if haversine_km(mlat, mlng, lat, lng) <= r_km:
            data["weight"] = data["base_weight"] * factor
            affected.append((u, v))
        else:
            data["weight"] = data["base_weight"]   # reset any prior inflation
    return affected


def reroute(G: nx.Graph, incident_latlng: tuple[float, float],
            origin_latlng: tuple[float, float] | None = None,
            dest_latlng: tuple[float, float] | None = None,
            radius_m: float | None = None,
            cfg: dict | None = None) -> dict:
    """Inflate the buffer around an incident and compute a diversion route.

    If origin/dest aren't given, we pick two nodes on opposite sides of the
    incident so the demo always has a meaningful path to bend.
    """
    cfg = cfg or load_config()
    d = cfg["diversion"]
    radius_m = radius_m or d["buffer_radius_m"]
    lat, lng = incident_latlng

    affected = _inflate(G, lat, lng, radius_m, d["cost_inflation"])

    # choose origin/dest if not supplied: nearest nodes ~1km on either side
    if origin_latlng is None:
        origin_latlng = (lat - 0.012, lng - 0.012)
    if dest_latlng is None:
        dest_latlng = (lat + 0.012, lng + 0.012)
    o = _nearest_node(G, *origin_latlng)
    t = _nearest_node(G, *dest_latlng)

    def _path_latlng(weight_attr):
        try:
            nodes = nx.shortest_path(G, o, t, weight=weight_attr)
            return [[G.nodes[n]["lat"], G.nodes[n]["lng"]] for n in nodes]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    diversion = _path_latlng("weight")        # inflated graph
    baseline = _path_latlng("base_weight")    # un-inflated

    return {
        "buffer_radius_m": radius_m,
        "affected_edge_count": len(affected),
        "affected_edges": [
            [[G.nodes[u]["lat"], G.nodes[u]["lng"]],
             [G.nodes[v]["lat"], G.nodes[v]["lng"]]] for u, v in affected
        ],
        "diversion_path": diversion,
        "baseline_path": baseline,
    }


if __name__ == "__main__":
    g = build_graph()
    out = reroute(g, (12.97, 77.59))
    log(f"affected edges: {out['affected_edge_count']}")
    log(f"baseline hops: {len(out['baseline_path']) if out['baseline_path'] else 0}, "
        f"diversion hops: {len(out['diversion_path']) if out['diversion_path'] else 0}")
