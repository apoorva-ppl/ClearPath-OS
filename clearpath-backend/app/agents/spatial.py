import asyncio
import functools
import math
from typing import Any, Literal

import networkx as nx

from app.core.config import get_settings
from app.core.state import IncidentInput, SpatialOutput

Waypoint = tuple[float, float]
NodeId = tuple[int, int]
GridGraph = nx.Graph

class SpatialRoutingError(RuntimeError):
 pass
#haversine_distance -> calculates the real world dist between 2 GPS coordinates
#euclidian can cause errors as lang n lat are on curved surfaces
def _haversine_distance(a: Waypoint, b: Waypoint) -> float:
    lat_a, lng_a = a
    lat_b, lng_b = b
    earth_radius_m = 6_371_000

    # Convert to radians
    lat_a_rad = math.radians(lat_a)
    lat_b_rad = math.radians(lat_b)
    delta_lat = math.radians(lat_b - lat_a)
    delta_lng = math.radians(lng_b - lng_a)

    # Haversine formula
    a_val = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a_rad) * math.cos(
        lat_b_rad
    ) * math.sin(delta_lng / 2) ** 2
    c_val = 2 * math.atan2(math.sqrt(a_val), math.sqrt(1 - a_val))

    return earth_radius_m * c_val


@functools.lru_cache(maxsize=4) #for efficiency
#creates bengaluru as a weighted graph
#each intersection=nodes , each road =edge , each dist = weight
def _build_base_grid(grid_resolution_m: int) -> GridGraph:
    # Bengaluru bbox 
    min_lat, max_lat = 12.77, 13.21
    min_lng, max_lng = 77.38, 77.74

    # Compute grid dimensions
    lat_range = max_lat - min_lat
    lng_range = max_lng - min_lng
    # Approximate metres per degree at equator: 111_111 m/degree
    lat_m_per_deg = 111_111
    lng_m_per_deg = 111_111 * math.cos(math.radians((min_lat + max_lat) / 2))

    n_rows = int(lat_range * lat_m_per_deg / grid_resolution_m)
    n_cols = int(lng_range * lng_m_per_deg / grid_resolution_m)

    # Build graph
    graph = nx.Graph()

    # Create nodes with lat/lng attributes
    for row in range(n_rows):
        for col in range(n_cols):
            lat = min_lat + (row / n_rows) * lat_range
            lng = min_lng + (col / n_cols) * lng_range
            graph.add_node((row, col), lat=lat, lng=lng)

    # Connect all 8 neighbors with Haversine weights
    for row in range(n_rows):
        for col in range(n_cols):
            node_a = (row, col)
            lat_a = graph.nodes[node_a]["lat"]
            lng_a = graph.nodes[node_a]["lng"]

            # 8 neighbors: N, NE, E, SE, S, SW, W, NW
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue  # Skip self
                    node_b = (row + dr, col + dc)
                    if node_b not in graph:
                        continue
                    lat_b = graph.nodes[node_b]["lat"]
                    lng_b = graph.nodes[node_b]["lng"]
                    dist = _haversine_distance(
                        (lat_a, lng_a), (lat_b, lng_b)
                    )
                    graph.add_edge(node_a, node_b, weight=dist)

    return graph

#simulates traffic congestion 
#instead of removing roads , we increase their costs
#removing may disconnect the graph (no paths -> application crash)
def _apply_congestion_mask(
    graph: GridGraph,
    incident: Waypoint,
    buffer_radius_m: float,
    inflation_factor: float,
) -> GridGraph:
    # Copy to avoid mutating the cached base grid
    congested = graph.copy()

    for node_a, node_b, attrs in congested.edges(data=True):
        lat_a = congested.nodes[node_a]["lat"]
        lng_a = congested.nodes[node_a]["lng"]
        lat_b = congested.nodes[node_b]["lat"]
        lng_b = congested.nodes[node_b]["lng"]

        # Check if either endpoint is inside the buffer
        dist_a = _haversine_distance(incident, (lat_a, lng_a))
        dist_b = _haversine_distance(incident, (lat_b, lng_b))

        if dist_a <= buffer_radius_m or dist_b <= buffer_radius_m:
            # Inflate the weight
            original_weight = attrs.get("weight", 1.0)
            congested[node_a][node_b]["weight"] = (
                original_weight * inflation_factor
            )

    return congested

#helps search nearest neighbour
def _nearest_node(graph: GridGraph, point: Waypoint) -> NodeId:
    
    if not graph.nodes:
        raise ValueError("Graph has no nodes; cannot snap point.")

    min_dist = float("inf")
    nearest = None

    for node in graph.nodes:
        lat = graph.nodes[node]["lat"]
        lng = graph.nodes[node]["lng"]
        dist = _haversine_distance(point, (lat, lng))
        if dist < min_dist:
            min_dist = dist
            nearest = node

    return nearest

#runs dijikstra's algo (shortest path between src n dest)
async def _calculate_single_route(
    graph: GridGraph,
    source: NodeId,
    target: NodeId,
) -> list[Waypoint]:

    def _blocking_dijkstra() -> list[NodeId]:
        """Blocking call to nx.shortest_path."""
        try:
            return nx.shortest_path(
                graph, source, target, weight="weight"
            )
        except nx.NetworkXNoPath as e:
            raise SpatialRoutingError(
                f"No path found from {source} to {target}"
            ) from e
        
    #thread pool
    #dijisktra is cpu intensive , if executed directly fastapi blocks
    #worker thread runs dijikstra (main thread free)
    node_path = await asyncio.to_thread(_blocking_dijkstra)

   
    # Convert node IDs to waypoints
    waypoints = []
    for node in node_path:
        lat = graph.nodes[node]["lat"]
        lng = graph.nodes[node]["lng"]
        waypoints.append((lat, lng))

    return waypoints

#calculates total route length 
def _path_distance_m(waypoints: list[Waypoint]) -> float:
    if len(waypoints) < 2:
        return 0.0
    total = 0.0
    for i in range(len(waypoints) - 1):
        total += _haversine_distance(waypoints[i], waypoints[i + 1])
    return total

#main function

class SpatialAgent:

    def __init__(self, settings: Any) -> None:
        self.settings = settings

    async def run(
        self,
        incident: IncidentInput,
        buffer_radius_m: float,
    ) -> SpatialOutput:
        
        # loads cached graph
        grid_resolution = self.settings.spatial.grid_resolution_m
        base_grid = _build_base_grid(grid_resolution)

        # Apply congestion mask
        inflation = self.settings.spatial.weight_inflation_factor
        congested_grid = _apply_congestion_mask(
            base_grid,
            (incident.lat, incident.lng),
            buffer_radius_m,
            inflation,
        )

        # finds nearest node
        incident_point = (incident.lat, incident.lng)
        source_node = _nearest_node(base_grid, incident_point)

        
        city_center = (13.0027, 77.5994)  # Bengaluru center (placeholder)
        target_node = _nearest_node(base_grid, city_center)

        # Calculate baseline route (no congestion)(represents normal traffic)
        baseline_path = await _calculate_single_route(
            base_grid,
            source_node,
            target_node,
        )

        # Calculate diversion route (with congestion)(represents traffic after incident)
        diversion_path = await _calculate_single_route(
            congested_grid,
            source_node,
            target_node,
        )
        #extra dist= diff of baseline route n diversion route
        # Counts delay(extra dist/avg speed =extra mins)
        nodes_affected = _count_nodes_in_buffer(
            base_grid,
            incident_point,
            buffer_radius_m,
        )

       
        baseline_distance_m = _path_distance_m(baseline_path)
        diversion_distance_m = _path_distance_m(diversion_path)
        delta_distance_m = max(0.0, diversion_distance_m - baseline_distance_m)

        avg_speed_kmh = self.settings.spatial.assumed_avg_speed_kmh
        avg_speed_m_per_min = (avg_speed_kmh * 1000) / 60
        delta_minutes = delta_distance_m / avg_speed_m_per_min

        return SpatialOutput(
            baseline_path=baseline_path,
            diversion_path=diversion_path,
            current_buffer_radius_m=buffer_radius_m,
            nodes_affected=nodes_affected,
            delta_distance_m=round(delta_distance_m, 1),
            delta_minutes=round(delta_minutes, 1),
            assumed_avg_speed_kmh=avg_speed_kmh,
        )

#counts nodes falling in affected area (to show how much of city network is impacted by incident)
def _count_nodes_in_buffer(
    graph: GridGraph,
    incident: Waypoint,
    buffer_radius_m: float,
) -> int:
    count = 0
    for node in graph.nodes:
        lat = graph.nodes[node]["lat"]
        lng = graph.nodes[node]["lng"]
        dist = _haversine_distance(incident, (lat, lng))
        if dist <= buffer_radius_m:
            count += 1
    return count



def create_spatial_agent(settings: Any | None = None) -> SpatialAgent:
    if settings is None:
        settings = get_settings()
    return SpatialAgent(settings)