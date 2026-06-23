# YAML parser, System Constants
# app/core/config.py
"""
Single source of truth for all configuration constants.

This module centralizes all configurable values (thresholds, costs, timeouts,
model paths, capacity limits) in a single, type-validated, immutable Settings
object. By reading from config.yaml exactly once and caching the result,
we ensure:

- No scattered magic numbers across 20 modules.
- All config changes are centralized and auditable.
- Test isolation: get_settings.cache_clear() resets state between test runs.
- Type safety: Pydantic validates every field at load time.
"""

import functools
import yaml
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SpatialSettings(BaseModel):
    """Graph and pathfinding configuration.
    
    Attributes:
        grid_resolution_m: Cell size in meters. 400 m balances granularity
            vs. memory cost for typical urban incident radius.
        base_buffer_radius_m: Buffer radius in meters (~2 city blocks,
            standard police cordon size).
        weight_inflation_factor: Edge weight multiplier to simulate gridlock.
            8x inflation mimics blocked corridors; below 5x, routers still
            prefer blocked corridors.
        assumed_avg_speed_kmh: Average urban driving speed used ONLY to
            convert delta_distance_m (real, graph-derived) into
            delta_minutes for the "commuter-minutes" ΔT metric. This is
            a disclosed modeling assumption, not measured or learned —
            there is no time/speed data in the road graph itself, only
            Haversine distance. 25 km/h reflects typical congested-city
            arterial speed; tune per city if reused elsewhere.
    """

    model_config = ConfigDict(frozen=True)

    grid_resolution_m: int = Field(
        default=400,
        gt=0,
        description="Cell size in meters."
    )
    base_buffer_radius_m: int = Field(
        default=800,
        gt=0,
        description="Buffer radius in meters."
    )
    weight_inflation_factor: float = Field(
        default=8.0,
        gt=0.0,
        description="Edge weight multiplier for blocked corridors."
    )
    assumed_avg_speed_kmh: float = Field(
        default=25.0,
        gt=0.0,
        description=(
            "Disclosed speed assumption for converting graph distance "
            "into a minutes estimate. NOT derived from data."
        ),
    )


class LogisticsSettings(BaseModel):
    """Resource allocation and dispatch constraints.
    
    Attributes:
        max_station_capacity: Maximum officers deployable from one station.
        max_dispatch_distance_km: Beyond this distance, travel time exceeds
            the golden-hour window for crowd-control deployment.
    """

    model_config = ConfigDict(frozen=True)

    max_station_capacity: int = Field(
        default=12,
        gt=0,
        description="Maximum officers per station."
    )
    max_dispatch_distance_km: float = Field(
        default=15.0,
        gt=0.0,
        description="Maximum dispatch distance in km."
    )


class SupervisorSettings(BaseModel):
    """Retry and expansion logic configuration.
    
    Attributes:
        max_expansion_attempts: Maximum number of radius expansion iterations.
        radius_expansion_multiplier: Geometric growth factor. 1.5x reaches
            city-wide coverage in 4 steps without overshooting.
    """

    model_config = ConfigDict(frozen=True)

    max_expansion_attempts: int = Field(
        default=4,
        gt=0,
        description="Maximum expansion iterations."
    )
    radius_expansion_multiplier: float = Field(
        default=1.5,
        gt=1.0,
        description="Geometric expansion factor."
    )


class ManpowerAllocation(BaseModel):
    """Officer and barricade counts for a severity tier.
    
    Attributes:
        officers: Number of officers to deploy.
        barricades: Number of barricade units to deploy.
    """

    model_config = ConfigDict(frozen=True)

    officers: int = Field(ge=0, description="Officer count.")
    barricades: int = Field(ge=0, description="Barricade count.")


class ManpowerMatrix(BaseModel):
    """Pre-computed resource allocations by severity tier.
    
    Pre-computed matrices avoid real-time ILP calls for simple, low-severity
    incidents, reducing latency on the critical path.
    
    Attributes:
        low: Allocation for low-severity incidents.
        medium: Allocation for medium-severity incidents.
        high: Allocation for high-severity incidents.
    """

    model_config = ConfigDict(frozen=True)

    low: ManpowerAllocation
    medium: ManpowerAllocation
    high: ManpowerAllocation


class BarricadeCosts(BaseModel):
    """Cost parameters for barricade operations.
    
    Attributes:
        cost_per_unit_per_hour: Cost to deploy and maintain one barricade
            unit per hour.
        max_budget_per_incident: Maximum allowed spend per incident.
    """

    model_config = ConfigDict(frozen=True)

    cost_per_unit_per_hour: float = Field(
        gt=0.0,
        description="Cost per barricade unit per hour."
    )
    max_budget_per_incident: float = Field(
        gt=0.0,
        description="Max budget per incident."
    )


class Settings(BaseModel):
    """
    Immutable, validated root configuration object.

    All settings are loaded from config.yaml at startup and cached for
    the process lifetime. The frozen=True constraint prevents accidental
    mutations at runtime, ensuring predictable behavior across the app.

    Attributes:
        spatial: Graph and pathfinding configuration.
        logistics: Resource allocation and dispatch configuration.
        supervisor: Retry and expansion logic configuration.
        manpower: Pre-computed resource allocations by severity.
        barricade: Barricade cost parameters.
    """

    model_config = ConfigDict(frozen=True)

    spatial: SpatialSettings
    logistics: LogisticsSettings
    supervisor: SupervisorSettings
    manpower: ManpowerMatrix
    barricade: BarricadeCosts
    model_dir: str = Field(
        default="models",
        description="Path to model artifacts directory.",
    )
    data_dir: str = Field(
        default="data/processed",
        description="Path to processed data directory.",
    )
    audio_dir: str = Field(
        default="app/static/audio",
        description="Path to audio output directory for synthesized dispatches.",
    )
    station_capacity: int = Field(
        default=12,
        gt=0,
        description="Default station officer capacity.",
    )
    host: str = Field(
        default="127.0.0.1",
        description="Uvicorn host.",
    )
    port: int = Field(
        default=8000,
        gt=0,
        description="Uvicorn port.",
    )
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins.",
    )


def _load_yaml_config() -> dict:
    """
    Load and parse config.yaml from the project root.

    Resolves the config file path relative to this module using pathlib,
    ensuring it works regardless of the working directory.

    Returns:
        Parsed YAML dictionary.

    Raises:
        RuntimeError: If config.yaml does not exist or is malformed.
    """
    config_path = Path(__file__).parent.parent.parent / "config.yaml"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError as e:
        raise RuntimeError(
            f"config.yaml not found at {config_path}. "
            "Ensure the file exists in the project root."
        ) from e
    except yaml.YAMLError as e:
        raise RuntimeError(
            f"config.yaml is malformed at {config_path}: {e}"
        ) from e


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Load and cache the application settings.

    Validates all fields using Pydantic constraints and freezes the
    object to prevent runtime mutations. Subsequent calls return the
    cached instance without re-reading or re-validating.

    To reset cache in tests, call: get_settings.cache_clear()

    Returns:
        Cached Settings object with all sub-configs validated.

    Raises:
        RuntimeError: If config.yaml is missing or malformed.
        ValidationError: If any field violates its Pydantic constraints.
    """
    raw_config = _load_yaml_config()
    return Settings(**raw_config)