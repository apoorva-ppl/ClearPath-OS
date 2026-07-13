from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

Waypoint = tuple[float, float]
"""Tuple of (latitude, longitude) in WGS-84."""

StationMap = dict[str, int]
"""Mapping of station_id to officer_count."""


class IncidentInput(BaseModel):

    model_config = ConfigDict(frozen=True)

    lat: float = Field(ge=-90.0, le=90.0, description="WGS-84 latitude.")
    lng: float = Field(ge=-180.0, le=180.0, description="WGS-84 longitude.")
    cause: str = Field(min_length=2, description="Human-readable incident cause.")
    priority: Literal["low", "medium", "high", "critical"] = Field(
        description="Initial severity assessment."
    )
    event_cause: str | None = Field(
        default=None,
        description="Real-pipeline cause category (e.g. tree_fall, accident).",
    )
    event_type: Literal["planned", "unplanned"] | None = Field(
        default=None, description="Whether the event was planned or unplanned."
    )
    corridor: str | None = Field(
        default=None, description="Named road corridor, if applicable."
    )
    start_datetime: str | None = Field(
        default=None, description="ISO-8601 incident start timestamp."
    )

class TriageOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity_tier: Literal["Low", "Medium", "High"] = Field(
        description="Severity tier predicted by LightGBM."
    )
    closure_prob: float = Field(
        ge=0.0, le=1.0, description="P(road closure) from model inference."
    )
    predicted_duration_minutes: int = Field(
        gt=0, description="Estimated incident duration in minutes."
    )
    model_version: str = Field(
        default="unknown",
        description="LightGBM artifact version for audit trail.",
    )


class SpatialOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_path: list[Waypoint] = Field(
        description="Original route waypoints (lat, lng)."
    )
    diversion_path: list[Waypoint] = Field(
        description="Rerouted path waypoints (lat, lng)."
    )
    current_buffer_radius_m: float = Field(
        gt=0.0, description="Current incident buffer radius in meters."
    )
    nodes_affected: int = Field(
        ge=0, description="Count of graph nodes inside the buffer."
    )
    delta_distance_m: float = Field(
        ge=0.0,
        description=(
            "Extra distance (meters) of diversion_path vs baseline_path. "
            "Computed by summing real Haversine edge weights along each "
            "path — not estimated or hardcoded."
        ),
    )
    delta_minutes: float = Field(
        ge=0.0,
        description=(
            "delta_distance_m converted to minutes using "
            "assumed_avg_speed_kmh. This is an explicit modeling "
            "assumption, not a measured travel time."
        ),
    )
    assumed_avg_speed_kmh: float = Field(
        gt=0.0,
        description=(
            "The average speed assumption used to derive delta_minutes "
            "from delta_distance_m. Sourced from settings.spatial — "
            "disclosed here so downstream consumers (directive, frontend) "
            "never mistake delta_minutes for a measured value."
        ),
    )


class LogisticsOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    assignments: StationMap = Field(
        description="Station → officer_count dispatch plan."
    )
    total_officers: int = Field(ge=0, description="Total officers in the dispatch plan.")
    total_barricades: int = Field(ge=0, description="Total barricade units in the plan.")
    feasible: bool = Field(description="True if ILP solver found a valid solution.")
    solver_status: str = Field(
        default="UNKNOWN", description="Raw OR-Tools solver status code."
    )


class SupervisorDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    should_escalate: bool = Field(
        description="True if escalation (radius expansion) is needed."
    )
    escalation_reason: str | None = Field(
        default=None, description="Reason for escalation, if any."
    )
    retry_count: int = Field(
        default=0, ge=0, description="Number of retry iterations."
    )
    expansion_applied: bool = Field(
        default=False,
        description="True if this state used an expanded buffer radius.",
    )


class DirectiveOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    tweet: str = Field(description="Twitter/X-style citizen alert.")
    sms: str = Field(description="SMS alert for buffer zone.")
    dispatch_script: str = Field(description="Police radio dispatch line.")
    dispatch_audio_url: str = Field(description="URL to synthesized dispatch audio.")



class PlanState(BaseModel):
    model_config = ConfigDict(frozen=True)

    incident: IncidentInput
    triage: TriageOutput | None = None
    spatial: SpatialOutput | None = None
    logistics: LogisticsOutput | None = None
    supervisor: SupervisorDecision | None = None
    directive: DirectiveOutput | None = None
    plan_id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique run ID for tracing.",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of state creation.",
    )
    stage: Literal[
        "init", "triage", "spatial", "logistics", "supervisor", "directive", "complete", "failed"
    ] = Field(
        default="init",
        description="Current pipeline stage (SSE progress signal).",
    )

    def advance(self, **updates: Any) -> "PlanState":
   
        return self.model_copy(update=updates)

class CityState(BaseModel):


    model_config = ConfigDict(arbitrary_types_allowed=True)

    stations: dict[str, dict] = Field(
        default_factory=dict,
        description="Mapping of station_id to station metadata.",
    )
    active_incidents: dict[str, dict] = Field(
        default_factory=dict,
        description="Mapping of incident_id to incident details and assigned resources.",
    )


class ModelArtifacts(BaseModel):

    model_config = ConfigDict(arbitrary_types_allowed=True)

    severity_model: Any = Field(
        description="LightGBM Booster for closure classification."
    )
    duration_model: Any = Field(
        description="LightGBM Booster for duration regression."
    )
    road_graph: Any = Field(
        description="NetworkX graph — OSMnx real streets or synthetic grid fallback."
    )
    station_data: Any = Field(
        description="DataFrame of station locations and capacities."
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Model evaluation metrics from models/metrics.json.",
    )
    graph_is_synthetic: bool = Field(
        default=False,
        description="True if road_graph is a synthetic grid, not real OSMnx streets.",
    )