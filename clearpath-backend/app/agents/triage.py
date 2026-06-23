# ML Inference Service (LightGBM)
# app/agents/triage.py
"""
Agent 1: LightGBM ML Inference + Rule-Based Severity Scoring.

Two-layer design:
  1. ML layer: LightGBM models infer closure_prob and duration.
  2. Rule layer: Deterministic point-scoring on top of ML output.

Why both layers:
  - ML produces probabilistic predictions, which are statistically accurate
    but hard for field commanders to interpret or justify to the public.
  - Point-scoring creates an auditable explanation chain: "High severity
    because: Accident (+3) + High Priority (+2) + Likely closure (+3) = 8
    points → High tier." This satisfies accountability requirements for
    public-safety AI systems.

The TriageAgent combines both to produce a final TriageOutput with a
severity tier, closure probability, and duration estimate.
"""

import asyncio
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.core.config import get_settings
from app.core.state import IncidentInput, TriageOutput


# ════════════════════════════════════════════════════════════════
# MOCK BOOSTER (temporary, replace with lightgbm import at deploy)
# ════════════════════════════════════════════════════════════════


class MockBooster:
    """
    Mock LightGBM Booster for local development without trained artifacts.

    Provides stable, deterministic predictions for unit testing.
    At deployment, replace with: `import lightgbm as lgb` and use
    `lgb.Booster(model_file=...)`.
    """

    def __init__(self, model_file: str) -> None:
        """
        Initialize mock booster.

        Args:
            model_file: Path to model artifact (for interface compatibility).
        """
        self.model_file = model_file

    def predict(self, data: list[list[float]]) -> list[float]:
        """
        Return stable dummy prediction matching LightGBM interface.

        Closure probability model returns [0.72] (above threshold).
        Duration model returns [45.0] (minutes).

        Args:
            data: Feature matrix of shape (n_samples, n_features).

        Returns:
            List of predictions matching number of input rows.
        """
        n_samples = len(data)
        if "duration" in self.model_file:
            return [45.0] * n_samples
        return [0.72] * n_samples


# ════════════════════════════════════════════════════════════════
# MODEL BUNDLE
# ════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ModelBundle:
    """
    Container for loaded model artifacts.

    Centralizes both models in one immutable object for easy
    dependency injection in tests and services.
    """

    severity_model: Any
    duration_model: Any


# ════════════════════════════════════════════════════════════════
# MODEL LOADING
# ════════════════════════════════════════════════════════════════


def _load_models(model_dir: Path) -> ModelBundle:
    """
    Load LightGBM model artifacts from disk.

    Attempts to load real lightgbm.Booster objects; falls back to
    MockBooster if lightgbm is not installed or artifacts are missing.

    Args:
        model_dir: Directory containing model artifacts.

    Returns:
        ModelBundle with both loaded boosters.

    Raises:
        FileNotFoundError: If artifacts don't exist and fallback fails.
    """
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


# ════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ════════════════════════════════════════════════════════════════


def _build_feature_vector(incident: IncidentInput) -> list[list[float]]:
    """
    Encode incident into a numeric feature vector for ML inference.

    Converts IncidentInput fields into numeric codes matching the exact
    feature schema used during training in features.py. Must stay in sync
    with the training pipeline — column order and encoding matter.

    Training features (10 total, in order):
      event_cause, event_type, corridor, hour, day_of_week,
      month, is_weekend, latitude, longitude, corridor_recent_count

    WHY we use current datetime for temporal features:
      - At inference time, we don't have historical timestamps.
      - We use the current moment as a proxy — an incident being
        reported NOW happened roughly NOW.
      - corridor_recent_count defaults to 0 (no rolling window at
        inference time without a live database query).

    Args:
        incident: Raw incident event data.

    Returns:
        Feature matrix with shape (1, 10) matching training schema.
        Nested list format required by lgb.Booster.predict().
    """
    from datetime import datetime, timezone

    # ── Categorical encodings (must match training label encoding) ──
    # LightGBM handles categoricals as integers; unknown → 0
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

    # ── Temporal features from current moment ──
    now = datetime.now(timezone.utc)
    hour = float(now.hour)
    day_of_week = float(now.weekday())   # 0=Monday, 6=Sunday
    month = float(now.month)
    is_weekend = float(now.weekday() >= 5)

    # ── Spatial features ──
    lat = float(incident.lat)
    lng = float(incident.lng)

    # ── Engineered feature ──
    # corridor_recent_count: 7-day rolling count at inference time.
    # Without a live DB query this defaults to 0 (conservative estimate).
    corridor_recent_count = 0.0

    # Return in exact training column order
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

# ════════════════════════════════════════════════════════════════
# POINT SCORING ENGINE
# ════════════════════════════════════════════════════════════════


def _compute_severity_points(
    incident: IncidentInput,
    closure_prob: float,
) -> int:
    """
    Compute auditable severity score via rule-based point system.

    Applies additive rules to produce an interpretable explanation.
    Worked Example:
      - Incident: cause="Accident", priority="high", closure_prob=0.65
      - Points: Accident (+3) + High Priority (+2) + Closure Likely (+3) = 8
      - Result: bin_severity(8) → "High"

    Args:
        incident: Raw incident data.
        closure_prob: Closure probability from ML model (0.0 to 1.0).

    Returns:
        Total integer points (typically 0-10 range).
    """
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


# ════════════════════════════════════════════════════════════════
# SEVERITY BINNING
# ════════════════════════════════════════════════════════════════


def _bin_severity(points: int) -> Literal["Low", "Medium", "High"]:
    """
    Convert point score into severity tier using config thresholds.

    Allows threshold tuning in config.yaml without Python changes.
    Thresholds: High ≥ 7, Medium ≥ 4, Low otherwise.

    Args:
        points: Severity point score.

    Returns:
        One of "Low", "Medium", or "High".
    """
    if points >= 7:
        return "High"
    elif points >= 4:
        return "Medium"
    return "Low"


# ════════════════════════════════════════════════════════════════
# TRIAGE AGENT
# ════════════════════════════════════════════════════════════════


class TriageAgent:
    """
    Triage classification agent using LightGBM + rule-based scoring.

    Single responsibility: take a raw IncidentInput, infer severity tier,
    closure probability, and duration using loaded models and point scoring.
    Does not coordinate with other agents — only communicates via PlanState.

    Attributes:
        model_bundle: Loaded severity and duration models.
    """

    def __init__(self, model_bundle: ModelBundle) -> None:
        """
        Initialize TriageAgent with loaded models.

        Args:
            model_bundle: Container of loaded LightGBM boosters.
        """
        self.model_bundle = model_bundle

    def run(self, incident: IncidentInput) -> TriageOutput:
        """
        Perform ML-based incident triage.

        Encodes the incident to features, runs LightGBM inference directly
        (sync), and combines ML output with rule-based point scoring to
        produce a final severity tier.

        Why run() is sync (not async):
          - generator.py wraps this call in asyncio.to_thread(), which
            runs the entire run() method in a threadpool executor.
          - Putting asyncio.to_thread() INSIDE run() would require run()
            to be async, but then generator.py's asyncio.to_thread(agent.run)
            would receive a coroutine object instead of a result — causing
            the "Unable to serialize unknown type: <class 'coroutine'>" error.
          - Rule: the boundary between async and sync is at the generator
            layer, not inside the agent. Agents are always sync.

        Args:
            incident: Raw incident event data.

        Returns:
            TriageOutput with severity tier, closure probability, and
            estimated duration.

        Raises:
            Exception: If model inference fails (implementation detail
                propagated from LightGBM).
        """
        features = _build_feature_vector(incident)

        # Direct sync call — thread-safety guaranteed by LightGBM's GIL release
        # asyncio.to_thread() in generator.py handles the event loop boundary
        closure_probs = self.model_bundle.severity_model.predict(features)
        closure_prob = float(closure_probs[0])

        durations = self.model_bundle.duration_model.predict(features)
        duration_minutes = int(round(np.expm1(durations[0])))

        # Compute rule-based severity score
        points = _compute_severity_points(incident, closure_prob)
        severity_tier = _bin_severity(points)

        return TriageOutput(
            severity_tier=severity_tier,
            closure_prob=closure_prob,
            predicted_duration_minutes=duration_minutes,
            model_version="v1.0",
        )

# ════════════════════════════════════════════════════════════════
# MODULE FACTORY
# ════════════════════════════════════════════════════════════════


def create_triage_agent(model_dir: Path | None = None) -> TriageAgent:
    """
    Factory function: construct a fully-initialized TriageAgent.

    Loads models from disk and wraps them in a TriageAgent instance.
    Called by app/api/deps.py during FastAPI app startup.

    Args:
        model_dir: Directory containing model artifacts. Defaults to
            "models/" relative to project root.

    Returns:
        Ready-to-use TriageAgent instance.

    Raises:
        FileNotFoundError: If model artifacts cannot be located.
    """
    if model_dir is None:
        model_dir = Path(__file__).parent.parent.parent / "models"

    bundle = _load_models(model_dir)
    return TriageAgent(bundle)