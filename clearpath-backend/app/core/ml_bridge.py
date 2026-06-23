# app/core/ml_bridge.py
"""
Bridge to the teammate's real ML pipeline (clearpath-os-dist).

WHY a separate bridge module instead of importing directly in generator.py:
  - clearpath-os-dist lives in a sibling directory, outside this package.
    We inject its path once, here, so the rest of the codebase never has
    to think about sys.path manipulation.
  - Isolates the "their dict-in/dict-out API" <-> "our Pydantic models"
    translation in one place. If their pipeline.py's function signatures
    change, only this file needs updating.
  - load_artifacts() does real file I/O (loads LightGBM boosters, builds
    a road graph, reads parquet) — expensive, so we cache it at module
    load time via lru_cache, mirroring how the FastAPI lifespan loads
    artifacts once at startup.
"""

import sys
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any
from app.core.state import IncidentInput
logger = logging.getLogger(__name__)

# ── Path injection ──────────────────────────────────────────────────────
# clearpath-os-dist is a SIBLING of this project (clearpath-backend), not
# a subpackage. We resolve its path relative to this file and add it to
# sys.path so `from src.pipeline import ...` resolves correctly.
_DIST_ROOT = Path(__file__).resolve().parents[2] / "clearpath-os-dist"

if str(_DIST_ROOT) not in sys.path:
    sys.path.insert(0, str(_DIST_ROOT))


@lru_cache(maxsize=1)
def get_ml_artifacts() -> dict[str, Any]:
    """
    Load and cache the real ML pipeline's artifacts (models, graph, stations).

    Cached via lru_cache so this expensive load (LightGBM boosters + road
    graph + station parquet) only happens once per process, mirroring the
    FastAPI lifespan pattern used for the mock ModelArtifacts.

    Returns:
        dict with keys: cfg, severity, duration, graph, stations
        (exact shape defined by clearpath-os-dist/src/pipeline.py).

    Raises:
        FileNotFoundError: If trained model files don't exist yet —
            run `python run_pipeline.py` in clearpath-os-dist first.
    """
    from src.pipeline import load_artifacts

    logger.info(f"ml_bridge: loading real ML artifacts from {_DIST_ROOT}")
    artifacts = load_artifacts()
    logger.info("ml_bridge: real ML artifacts loaded successfully")
    return artifacts


def run_real_pipeline(incident: "IncidentInput") -> dict[str, Any]:
    """
    Run the real, trained ML pipeline for one incident.

    Translates our IncidentInput (Pydantic, frozen) into the dict shape
    their plan_incident() expects, then calls it.

    WHY a flat dict and not their Pydantic equivalent:
      - Their pipeline.py is intentionally dependency-light (no Pydantic),
        so it takes/returns plain dicts. We honor that boundary rather
        than forcing them to adopt our schema.

    Args:
        incident: Our IncidentInput. `event_cause`, `event_type`,
            `corridor`, `start_datetime` are optional on our side;
            sensible defaults are substituted here if absent, matching
            the defaults inside their own _incident_to_features().

    Returns:
        The full plan dict from plan_incident(): incident, severity,
        severity_detail, closure, duration, diversion, allocation,
        supervisor, directive (if with_directive=True).
    """
    art = get_ml_artifacts()

    inc_dict = {
        "id": f"INC-{incident.lat:.4f}-{incident.lng:.4f}",
        "lat": incident.lat,
        "lng": incident.lng,
        "event_cause": incident.event_cause or "others",
        "event_type": incident.event_type or "unplanned",
        "corridor": incident.corridor or "Non-corridor",
        "start_datetime": incident.start_datetime,
    }

    from src.pipeline import plan_incident

    return plan_incident(inc_dict, art, with_directive=True)