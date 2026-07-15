import functools
import yaml
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field

class SpatialSettings(BaseModel):
    
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
    model_config = ConfigDict(frozen=True)

    officers: int = Field(ge=0, description="Officer count.")
    barricades: int = Field(ge=0, description="Barricade count.")


class ManpowerMatrix(BaseModel):
    model_config = ConfigDict(frozen=True)

    low: ManpowerAllocation
    medium: ManpowerAllocation
    high: ManpowerAllocation


class BarricadeCosts(BaseModel):
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
    raw_config = _load_yaml_config()
    return Settings(**raw_config)