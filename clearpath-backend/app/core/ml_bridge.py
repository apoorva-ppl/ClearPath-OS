import sys
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any
from app.core.state import IncidentInput

logger = logging.getLogger(__name__)

#finds where ML project is stored
_DIST_ROOT = Path(__file__).resolve().parents[1] / "clearpath-os-dist"
if str(_DIST_ROOT) not in sys.path:
    sys.path.insert(0, str(_DIST_ROOT))

#LRU Cache
#ML models are large and expensive to load
#cache them n reuse them for every API request, improving performance.
@lru_cache(maxsize=1)
def get_ml_artifacts() -> dict[str, Any]:
    from src.pipeline import load_artifacts  # type: ignore
    logger.info(f"ml_bridge: loading real ML artifacts from {_DIST_ROOT}")
    artifacts = load_artifacts()
    logger.info("ml_bridge: real ML artifacts loaded successfully")
    return artifacts

#main function
#recieves incident -> loads model -> converts incident -> call ml pipeline -> returns prediction
def run_real_pipeline(incident: "IncidentInput") -> dict[str, Any]:
    art = get_ml_artifacts()
    #a simple translator ,( incident output-> dictionary -> ml pipeline)
    inc_dict = {
        "id": f"INC-{incident.lat:.4f}-{incident.lng:.4f}",
        "lat": incident.lat,
        "lng": incident.lng,
        "event_cause": incident.event_cause or "others", #safe fallback
        "event_type": incident.event_type or "unplanned",
        "corridor": incident.corridor or "Non-corridor",
        "start_datetime": incident.start_datetime,
    }
    from src.pipeline import plan_incident  # type: ignore
    return plan_incident(inc_dict, art, with_directive=True)