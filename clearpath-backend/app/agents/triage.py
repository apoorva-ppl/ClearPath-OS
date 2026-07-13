import asyncio
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.core.config import get_settings
from app.core.state import IncidentInput, TriageOutput


#dummy model used when trained models are unavailable
class MockBooster:
    def __init__(self, model_file: str) -> None:
        self.model_file = model_file

    def predict(self, data: list[list[float]]) -> list[float]:
        n_samples = len(data)
        if "duration" in self.model_file:
            return [45.0] * n_samples
        return [0.72] * n_samples

#module bundle, groups both the Severity Model and Duration Model into one object, making dependency injection and passing models throughout the application much cleaner.
@dataclass(frozen=True)
class ModelBundle:
    severity_model: Any
    duration_model: Any


#loads bundle , looks for both the files , loads them if fails to load use mockbooster
def _load_models(model_dir: Path) -> ModelBundle:
    severity_path = model_dir / "severity.txt"
    duration_path = model_dir / "duration.txt"

    try:
        import lightgbm

        severity_model = lightgbm.Booster(model_file=str(severity_path))
        duration_model = lightgbm.Booster(model_file=str(duration_path))
    except (ImportError, FileNotFoundError) as e:
        # Fallback to mock for local development
        print(f"⚠️  WARNING: Real LightGBM models failed to load ({e}). "
              f"Using MockBooster — ALL predictions will be FAKE "
              f"(severity=0.72, duration=45min for every incident).")
        severity_model = MockBooster(str(severity_path))
        duration_model = MockBooster(str(duration_path))

    return ModelBundle(
        severity_model=severity_model,
        duration_model=duration_model,
    )


#This function converts the incoming live incident into exactly the same feature vector that the model saw during training.
def _build_feature_vector(incident: IncidentInput) -> list[list[float]]:

    from datetime import datetime, timezone

    
    # ml models cant understand string so categorical values converted to numeric codes.
    cause_map = {
        "vehicle_breakdown": 0,
        "accident": 1,
        "tree_fall": 2,
        "water_logging": 3,
        "pot_holes": 4,
        "public_event": 5,
        "construction": 6,
        "procession": 7,
        "protest": 8,
        "vip_movement": 9,
        "others": 10,
    }
    event_type_map = {"unplanned": 0, "planned": 1}
    # corridor: unknown corridors map to 0 (Non-corridor equivalent)
    corridor_map = {
        "Non-corridor": 0,
        "Tumkur Road": 1,
        "ORR East 1": 2,
        "ORR East 2": 3,
        "ORR West 1": 4,
        "ORR West 2": 5,
        "Hosur Road": 6,
        "Mysore Road": 7,
        "Bellary Road": 8,
        "Bannerghatta Road": 9,
    }

    cause_code = float(cause_map.get(incident.cause.lower(), 10))
    # event_type not in IncidentInput — default to unplanned (0)
    event_type_code = 0.0
    # corridor not in IncidentInput — default to Non-corridor (0)
    corridor_code = 0.0

    # Temporal features from current moment 
    now = datetime.now(timezone.utc)
    hour = float(now.hour)
    day_of_week = float(now.weekday())   # 0=Monday, 6=Sunday
    month = float(now.month)
    is_weekend = float(now.weekday() >= 5)

   #spatial feature
    lat = float(incident.lat)
    lng = float(incident.lng)

    #engineered feature
    corridor_recent_count = 0.0

    # Return in exact training column order
    #Because the model was trained on this exact column order. Changing the order would feed incorrect values into the wrong features and produce invalid predictions.
    return [[
        cause_code,           # event_cause
        event_type_code,      # event_type
        corridor_code,        # corridor
        hour,                 # hour
        day_of_week,          # day_of_week
        month,                # month
        is_weekend,           # is_weekend
        lat,                  # latitude
        lng,                  # longitude
        corridor_recent_count,  # corridor_recent_count
    ]]

#point scoring engine
#The ML model predicts probabilities, but field officers need explainable decisions, predictions into a transparent point system
def _compute_severity_points(
    incident: IncidentInput,
    closure_prob: float,
) -> int:
  
    points = 0

    # Cause points (thresholds from config, hardcoded for now)
    cause_points_map = {
        "accident": 3,
    "water_logging": 3,
    "tree_fall": 3,
    "fire": 4,
    "vip_movement": 2,
    "vehicle_breakdown": 1,
    "pot_holes": 1,
    "public_event": 1,
    "construction": 1,
    "procession": 1,
    "protest": 2,
    "others": 1,
    }
    points += cause_points_map.get(incident.cause.lower(), 1)

    # Priority points
    if incident.priority in ("high", "critical"):
        points += 2
    elif incident.priority == "medium":
        points += 1

    # Closure probability points (threshold: 0.5)
    if closure_prob >= 0.5:
        points += 3

    return points


#severity binning
#points to severity(high/low/med)
def _bin_severity(points: int) -> Literal["Low", "Medium", "High"]:
  
    if points >= 7:
        return "High"
    elif points >= 4:
        return "Medium"
    return "Low"


#triage agent
#encapsulation of entire prediction workflow , only use run()
class TriageAgent:
    def __init__(self, model_bundle: ModelBundle) -> None:
        """
        Initialize TriageAgent with loaded models.

        Args:
            model_bundle: Container of loaded LightGBM boosters.
        """
        self.model_bundle = model_bundle

    def run(self, incident: IncidentInput) -> TriageOutput:
       
        features = _build_feature_vector(incident) #raw incidents to ml features


        closure_probs = self.model_bundle.severity_model.predict(features)
        closure_prob = float(closure_probs[0])

        durations = self.model_bundle.duration_model.predict(features)
        duration_minutes = int(round(np.expm1(durations[0])))

        # Compute rule-based severity score
        points = _compute_severity_points(incident, closure_prob)
        severity_tier = _bin_severity(points)

        return TriageOutput( #api gets all of these
            severity_tier=severity_tier,
            closure_prob=closure_prob,
            predicted_duration_minutes=duration_minutes,
            model_version="v1.0",
        )


#It loads the trained models, creates the TriageAgent, and returns a fully initialized object so the FastAPI application can use it immediately.

def create_triage_agent(model_dir: Path | None = None) -> TriageAgent:
   
    if model_dir is None:
        model_dir = Path(__file__).parent.parent.parent / "models"

    bundle = _load_models(model_dir)
    return TriageAgent(bundle)