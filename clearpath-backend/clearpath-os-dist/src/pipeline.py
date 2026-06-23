"""
pipeline.py  —  the orchestrator (Stage 9).

This is the "agentic pipeline" — implemented honestly as a deterministic state
machine with a feasibility-driven re-planning loop. Each step below maps to one
"agent" in the pitch narrative, but they always run in fixed order, so they are
just functions. The Supervisor's "conditional loop" is a real `while` loop that
expands the diversion radius and re-optimises until the plan is feasible (or the
expansion budget is exhausted).

ONE incident in  ->  one complete operational plan out:

  predict_severity  (Triage)        : features -> Low/Medium/High + probs
  estimate_duration (Triage)        : features -> minutes + tier display
  reroute           (Spatial Graph) : inflate buffer -> diversion path
  allocate          (Logistics)     : stations x incidents -> assignment
  feasibility loop  (Supervisor)    : if uncovered -> grow radius, re-route, re-allocate
  generate_directive(Reporting)     : plan JSON -> directive text + PDF

Public API:
  load_artifacts()  -> dict of loaded models/graph/stations (call once)
  plan_incident(incident, artifacts) -> full plan dict

Run (self-test): python -m src.pipeline
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from .features import FEATURE_COLS
from .optimize_resources import allocate
from .route_diversion import build_graph, reroute
from .directive_llm import generate_directive
from .utils import load_config, resolve, log
from pathlib import Path

LEVEL_NAME = {0: "Low", 1: "Medium", 2: "High"}


# ----------------------------------------------------------- artifact load ----
BASE_DIR = Path(__file__).resolve().parent.parent
def load_artifacts(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    sev = lgb.Booster(model_file=str(resolve(cfg["paths"]["severity_model"])))
    dur = lgb.Booster(model_file=str(resolve(cfg["paths"]["duration_model"])))
    graph = build_graph(cfg)
    stations = synth_stations(cfg)
    log(f"pipeline: loaded models + graph + {len(stations)} stations")
    return {"cfg": cfg, "severity": sev, "duration": dur,
            "graph": graph, "stations": stations}


def synth_stations(cfg: dict) -> list[dict]:
    """Synthesise a station roster from the data's police_station column.

    Each distinct police_station -> one station node located at the centroid of
    the incidents handled there, with a uniform officer capacity from config.
    """
    df = pd.read_parquet(resolve(cfg["paths"]["clean_parquet"]))
    grp = df.groupby("police_station").agg(
        lat=("latitude", "mean"), lng=("longitude", "mean")).reset_index()
    cap = cfg["resources"]["station_capacity"]
    return [{"station": r.police_station, "lat": r.lat, "lng": r.lng,
             "capacity": cap} for r in grp.itertuples()]


# --------------------------------------------------------- feature builder ----
def _incident_to_features(inc: dict, cfg: dict) -> pd.DataFrame:
    """Turn a raw incident dict into the model feature row.

    Required keys: lat, lng, event_cause, event_type, start_datetime (ISO str).
    Optional: corridor, corridor_recent_count.
    """
    ts = pd.Timestamp(inc.get("start_datetime") or pd.Timestamp.now("UTC"))
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    row = {
        "event_cause": inc.get("event_cause", "others"),
        "event_type": inc.get("event_type", "unplanned"),
        "corridor": inc.get("corridor", "Non-corridor"),
        "hour": ts.hour, "dow": ts.dayofweek, "month": ts.month,
        "is_weekend": int(ts.dayofweek in (5, 6)),
        "latitude": inc["lat"], "longitude": inc["lng"],
        "corridor_recent_count": inc.get("corridor_recent_count", 0),
    }
    X = pd.DataFrame([row])[FEATURE_COLS]
    for c in ("event_cause", "event_type", "corridor"):
        X[c] = X[c].astype("category")
    return X


def _duration_display(minutes: float) -> str:
    if minutes < 60:
        return f"~{int(minutes)} min (<1h tier)"
    if minutes <= 240:
        h, m = divmod(int(minutes), 60)
        return f"~{h}h {m}m (1-4h tier)"
    h = minutes / 60
    return f"~{h:.1f}h (4h+ tier)"


# --------------------------------------------------------------- the plan ----
def _derive_severity(closure_prob: float, dur_min: float, cause: str,
                     cfg: dict) -> tuple[str, dict]:
    """Derive the DISPLAY severity tier from learned predictions.

    Inputs that are all model-driven or auditable:
      - closure_prob : P(requires road closure) from the classifier   [learned]
      - dur_min      : predicted clearance minutes                     [learned]
      - cause        : event cause -> cause_points from the rubric     [rule]
    We map these to a 0..N score with the SAME weighting philosophy as the
    offline rubric, but using PREDICTED closure (not the true flag) so it works
    at inference time when the closure decision isn't yet known.
    """
    s = cfg["severity"]
    score = 0.0
    # closure contribution scales with predicted probability
    score += closure_prob * s["closure_points"]
    # cause contribution (rule)
    score += s["cause_points"].get(cause, s["default_cause_points"])
    # duration tier contribution (from the duration model)
    if dur_min > 240:
        score += s["duration_points"]["over_240_min"]
    elif dur_min > 60:
        score += s["duration_points"]["over_60_min"]

    bins = s["bins"]
    if score >= bins["high_min"]:
        level = "High"
    elif score >= bins["medium_min"]:
        level = "Medium"
    else:
        level = "Low"
    return level, {"score": round(score, 2),
                   "closure_probability": round(float(closure_prob), 3)}


def plan_incident(inc: dict, art: dict, with_directive: bool = True) -> dict:
    cfg = art["cfg"]

    # --- Triage: predictions (closure probability + duration) ---
    X = _incident_to_features(inc, cfg)
    closure_prob = float(art["severity"].predict(X)[0])   # binary model -> P(closure)
    dur_min = max(0.0, float(np.expm1(art["duration"].predict(X)[0])))

    # --- derive DISPLAY severity from the learned predictions ---
    severity, sev_detail = _derive_severity(
        closure_prob, dur_min, inc.get("event_cause", "others"), cfg)

    # predicted closure decision (threshold), unless the caller forced a value
    predicted_closure = closure_prob >= cfg.get("closure_threshold", 0.5)
    requires_closure = inc.get("requires_road_closure", predicted_closure)

    inc_id = inc.get("id", "SIM-0001")
    incident_full = {**inc, "id": inc_id, "severity": severity,
                     "requires_road_closure": requires_closure,
                     "predicted_closure_prob": round(closure_prob, 3)}

    # --- Supervisor feedback loop: route + allocate, grow radius if uncovered ---
    d = cfg["diversion"]
    radius = d["buffer_radius_m"]
    expansions = 0
    diversion = allocation = None
    while True:
        diversion = reroute(art["graph"], (inc["lat"], inc["lng"]),
                            radius_m=radius, cfg=cfg)
        allocation = allocate([{"id": inc_id, "lat": inc["lat"], "lng": inc["lng"],
                                "severity": severity,
                                "requires_road_closure":
                                    incident_full["requires_road_closure"]}],
                              art["stations"], cfg)
        if allocation["feasible"] or expansions >= d["max_radius_expansions"]:
            break
        radius *= d["radius_growth"]
        expansions += 1
        log(f"pipeline: incident uncovered -> expanding radius to {int(radius)}m "
            f"(expansion {expansions})")

    plan = {
        "incident": incident_full,
        "severity": severity,
        "severity_detail": sev_detail,
        "closure": {"probability": round(closure_prob, 3),
                    "predicted": bool(predicted_closure)},
        "duration": {"minutes": round(dur_min, 1),
                     "display": _duration_display(dur_min)},
        "diversion": diversion,
        "allocation": allocation,
        "supervisor": {"radius_expansions": expansions,
                       "final_radius_m": int(radius),
                       "feasible": allocation["feasible"]},
    }

    if with_directive:
        directive = generate_directive(plan, cfg=cfg)
        plan["directive"] = directive

    return plan


if __name__ == "__main__":
    art = load_artifacts()
    # tree_fall on a corridor: the closure classifier should predict elevated
    # closure risk here (tree-falls drive most real closures in the data), so
    # severity is derived from the model, not a forced flag.
    sample = {
        "id": "SIM-DEMO", "event_cause": "tree_fall", "event_type": "unplanned",
        "corridor": "Sankey Road", "lat": 13.0061, "lng": 77.5794,
        "start_datetime": "2024-03-08T18:30:00+00:00",
    }
    result = plan_incident(sample, art)
    import json
    # print everything except the bulky affected_edges list
    slim = {**result}
    slim["diversion"] = {k: v for k, v in result["diversion"].items()
                         if k != "affected_edges"}
    slim["directive"] = {"pdf_path": result["directive"]["pdf_path"]}
    print(json.dumps(slim, indent=2, default=str))
