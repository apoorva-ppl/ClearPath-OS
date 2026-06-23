# app/core/state.py
"""
Centralized, immutable state contract for the 4-agent pipeline.

All agents communicate exclusively through PlanState, a frozen Pydantic
object. This design decouples agents (they depend on the schema, not each
other) and enables deterministic SSE streaming—each event is a snapshot
of the exact state at that stage.

Since state is frozen, agents cannot mutate in place. Instead, they use
`.model_copy(update={...})` or the `advance()` helper to produce the
next state. This creates an auditable chain, essential for debugging
distributed, asynchronous workflows.

Type Aliases:
    Waypoint: Tuple of (lat, lng) coordinates.
    StationMap: Mapping of station_id to officer_count.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# ════════════════════════════════════════════════════════════════
# TYPE ALIASES
# ════════════════════════════════════════════════════════════════

Waypoint = tuple[float, float]
"""Tuple of (latitude, longitude) in WGS-84."""

StationMap = dict[str, int]
"""Mapping of station_id to officer_count."""


# ════════════════════════════════════════════════════════════════
# LEAF MODELS (no internal dependencies)
# ════════════════════════════════════════════════════════════════


class IncidentInput(BaseModel):
    """
    Raw event payload received from the API layer.

    Attributes:
        lat: WGS-84 latitude of the incident center.
        lng: WGS-84 longitude of the incident center.
        cause: Human-readable label describing the incident type
            (e.g., "Protest", "Traffic Accident").
        priority: Severity flag used to seed triage inference.
    """

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
    """
    Structured result from the LightGBM triage agent.

    Attributes:
        severity_tier: Predicted severity category from the ML model.
        closure_prob: Probability of road closure (0.0 to 1.0).
        predicted_duration_minutes: Estimated incident duration.
        model_version: Version tag of the LightGBM artifact. Enables
            detection of prediction drift when the artifact is updated.
    """

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
    """
    Structured result from the NetworkX spatial pathfinding agent.

    Attributes:
        baseline_path: Ordered waypoints of the original, pre-incident route.
        diversion_path: Ordered waypoints of the rerouted path avoiding
            the incident buffer.
        current_buffer_radius_m: Radius (in meters) used to define the
            incident zone. May grow via supervisor expansion.
        nodes_affected: Count of graph nodes inside the buffer zone.
            Used by the supervisor to justify radius expansion.
        delta_distance_m: Extra distance of diversion vs baseline route,
            computed from real graph edge weights.
        delta_minutes: delta_distance_m converted to minutes via an
            explicit assumed average speed (see assumed_avg_speed_kmh).
        assumed_avg_speed_kmh: The disclosed speed assumption used for
            the delta_minutes conversion.
    """

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
    """
    Structured result from the OR-Tools resource optimization agent.

    Attributes:
        assignments: Mapping of station_id to officer_count for dispatch.
        total_officers: Sum of all officers assigned.
        total_barricades: Total barricade units deployed.
        feasible: False if the ILP solver found no valid solution.
        solver_status: Raw status string from OR-Tools (e.g., OPTIMAL,
            INFEASIBLE, MODEL_INVALID). Enables the supervisor to
            distinguish infeasible failures from timeout failures.
    """

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
    """
    Supervisor's verdict after reviewing all agent outputs.

    Attributes:
        should_escalate: True if an agent failed and retry with expanded
            radius is needed.
        escalation_reason: If should_escalate is True, a string explaining
            why (e.g., "Infeasible resource allocation").
        retry_count: Number of times the pipeline has been retried with
            expanded radius.
        expansion_applied: True if the current state resulted from a
            radius expansion.
    """

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
    """
    Crisis communications outputs for citizens and police.

    Generated after supervisor loop completes successfully (only if plan
    was not escalated). Contains three outputs: tweet (citizen alert),
    SMS (buffer zone warning), and dispatch script (police radio).
    The audio URL points to the synthesized MP3 broadcast version of
    the dispatch script.

    Attributes:
        tweet: Twitter/X-style alert (~280 chars) with severity, cause,
               corridor, duration, and officer count.
        sms: Plain-text SMS alert for citizens in buffer zone, with
             radius and estimated clearance time.
        dispatch_script: Police radio dispatch line with location,
                        severity, units, and clearance time.
        dispatch_audio_url: URL to synthesized MP3 audio file
                           (e.g., "/audio/dispatch_a1b2c3d4.mp3").
    """

    model_config = ConfigDict(frozen=True)

    tweet: str = Field(description="Twitter/X-style citizen alert.")
    sms: str = Field(description="SMS alert for buffer zone.")
    dispatch_script: str = Field(description="Police radio dispatch line.")
    dispatch_audio_url: str = Field(description="URL to synthesized dispatch audio.")


# ════════════════════════════════════════════════════════════════
# ROOT MODEL
# ════════════════════════════════════════════════════════════════


class PlanState(BaseModel):
    """
    Single, immutable state object for the entire 4-agent pipeline.

    The `stage` field is the single source of truth for SSE progress;
    the generator inspects this to determine what to emit rather than
    checking which sub-models are None.

    All agents receive a PlanState, produce updates, and return a new
    PlanState via `advance()`. This creates an auditable chain of
    snapshots for end-to-end debugging.

    Attributes:
        incident: Raw incident input data.
        triage: LightGBM inference result (None until triage stage).
        spatial: NetworkX pathfinding result (None until spatial stage).
        logistics: OR-Tools optimization result (None until logistics).
        supervisor: Supervisor's decision on escalation (None until
            supervisor stage).
        directive: Crisis communications outputs (None until directive stage).
        plan_id: Unique run ID for end-to-end tracing.
        created_at: Timestamp when this state was created.
        stage: Current pipeline stage; determines SSE event content.
    """

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
        """
        Return a new PlanState with the given fields updated.

        Because PlanState is frozen, agents cannot mutate state in place.
        This method enforces the immutable-update pattern:
            next_state = current_state.advance(
                triage=triage_result,
                stage="spatial"
            )

        This creates an auditable chain of snapshots for debugging and
        replay.

        Args:
            **updates: Field name and new value pairs.

        Returns:
            A new PlanState with the specified fields updated.

        Raises:
            ValidationError: If an update violates Pydantic constraints.
        """
        return self.model_copy(update=updates)


# ════════════════════════════════════════════════════════════════
# OPERATIONAL STATE MODELS (mutable, live city state)
# ════════════════════════════════════════════════════════════════


class CityState(BaseModel):
    """
    Live, mutable operational state of the city during disaster response.

    Unlike PlanState (which is frozen and immutable), CityState tracks the
    real-time state of the city: which stations are available, how many
    officers are deployed, which incidents are active, etc.

    This model is mutated by the pipeline after a plan is finalized and
    committed (e.g., decrementing available officers at dispatched stations,
    adding the new incident to the active list).

    Attributes:
        stations: Dictionary mapping station_id to station metadata
                  (officer count, availability). Defaults to empty.
        active_incidents: Dictionary mapping incident_id to incident
                         metadata (details, assigned resources).
                         Defaults to empty.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    stations: dict[str, dict] = Field(
        default_factory=dict,
        description="Mapping of station_id to station metadata.",
    )
    active_incidents: dict[str, dict] = Field(
        default_factory=dict,
        description="Mapping of incident_id to incident details and assigned resources.",
    )


# ════════════════════════════════════════════════════════════════
# ARTIFACT MODEL (loaded once at lifespan startup)
# ════════════════════════════════════════════════════════════════


class ModelArtifacts(BaseModel):
    """
    Container for all ML artifacts loaded once at application startup.

    Stored on app.state by the lifespan context manager in main.py and
    injected into every endpoint via deps.py. Never re-loaded per request.

    WHY arbitrary_types_allowed:
        Pydantic cannot validate lgb.Booster or nx.Graph natively —
        they have no JSON schema representation. Setting
        arbitrary_types_allowed=True tells Pydantic to store them
        as-is and skip validation. This is correct here because these
        objects are read-only after startup and never serialized.

    Attributes:
        severity_model: LightGBM Booster for road closure classification.
        duration_model: LightGBM Booster for clearance time regression.
        road_graph: NetworkX graph of the Bengaluru road network.
                    Either loaded from bengaluru.graphml (OSMnx) or a
                    synthetic 400m grid graph as fallback.
        station_data: DataFrame of police station locations and capacities,
                      derived from historical incident centroids.
        metrics: Dict loaded from models/metrics.json — ROC-AUC, PR-AUC,
                 median-AE, and feature importance for the Model Card page.
        graph_is_synthetic: True if road_graph is a fallback grid, not
                            real OSMnx streets. Surfaced in the Model Card
                            as a transparency flag.
    """

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