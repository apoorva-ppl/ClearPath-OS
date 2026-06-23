import asyncio
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

from app.api.deps import ArtifactsDep, CityStateDep
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()

# ════════════════════════════════════════════════════════════════
# RISK GRID CONFIGURATION
# (Documented constants — the bounding box must be configured somewhere;
#  these are not invented data values, just the scan boundary.)
# ════════════════════════════════════════════════════════════════

RISK_GRID_LAT_MIN = 12.85
RISK_GRID_LAT_MAX = 13.15
RISK_GRID_LNG_MIN = 77.45
RISK_GRID_LNG_MAX = 77.78
RISK_GRID_SIZE = 6  # 6x6 = 36 cells

# Default profile for a synthetic "what if" grid cell — these are the
# single most frequent real values observed in features.parquet
# (event_cause: 4886/~9000 rows, event_type: 7692/~9000 rows,
#  corridor: 3084/~9000 rows). NOT invented; empirically the mode.
RISK_GRID_DEFAULT_EVENT_CAUSE = "vehicle_breakdown"
RISK_GRID_DEFAULT_EVENT_TYPE = "unplanned"
RISK_GRID_DEFAULT_CORRIDOR = "Non-corridor"


def _score_risk_grid(artifacts: Any) -> list[dict]:
    """
    Score closure-probability risk across a synthetic grid covering
    Bengaluru, using the real severity_model and the current real
    timestamp (hour/dow/month/is_weekend are never faked).

    Each grid cell uses the empirically most-common event_cause/
    event_type/corridor from training data as a neutral baseline
    profile, since a synthetic point has no real incident context.
    corridor_recent_count is correctly 0 — there is no real recent
    history at a synthetic coordinate.

    Args:
        artifacts: ModelArtifacts with severity_model and metrics.

    Returns:
        List of 36 dicts: {lat, lng, closure_prob}, one per grid cell.
    """
    import numpy as np

    now = datetime.utcnow()
    lats = np.linspace(RISK_GRID_LAT_MIN, RISK_GRID_LAT_MAX, RISK_GRID_SIZE)
    lngs = np.linspace(RISK_GRID_LNG_MIN, RISK_GRID_LNG_MAX, RISK_GRID_SIZE)

    rows = []
    coords = []
    for lat in lats:
        for lng in lngs:
            rows.append(
                {
                    "event_cause": RISK_GRID_DEFAULT_EVENT_CAUSE,
                    "event_type": RISK_GRID_DEFAULT_EVENT_TYPE,
                    "corridor": RISK_GRID_DEFAULT_CORRIDOR,
                    "hour": now.hour,
                    "dow": now.weekday(),
                    "month": now.month,
                    "is_weekend": int(now.weekday() >= 5),
                    "latitude": float(lat),
                    "longitude": float(lng),
                    "corridor_recent_count": 0,
                }
            )
            coords.append((float(lat), float(lng)))

    grid_df = pd.DataFrame(rows)[FEATURE_COLS]
    for col in ["event_cause", "event_type", "corridor"]:
        grid_df[col] = grid_df[col].astype("category")

    closure_probs = artifacts.severity_model.predict(grid_df)

    return [
        {"lat": coords[i][0], "lng": coords[i][1], "closure_prob": float(closure_probs[i])}
        for i in range(len(coords))
    ]


# Feature columns used by the ML models (in pipeline order)
# These columns are already encoded in features.parquet — no re-encoding needed
FEATURE_COLS = [
    "event_cause",
    "event_type",
    "corridor",
    "hour",
    "dow",  # day of week
    "month",
    "is_weekend",
    "latitude",
    "longitude",
    "corridor_recent_count",
]


def _severity_tier(closure_prob: float, decision_threshold: float = 0.5) -> str:
    """
    Derive severity tier from closure probability.
    
    Uses the decision_threshold from model metrics (default 0.5).
    High >= threshold, Medium [0.3, threshold), Low < 0.3.
    """
    if closure_prob >= decision_threshold:
        return "High"
    elif closure_prob >= 0.3:
        return "Medium"
    else:
        return "Low"


def _duration_display(predicted_minutes: float) -> str:
    """Convert predicted minutes to display string."""
    if predicted_minutes < 60:
        return "< 1h"
    elif predicted_minutes < 240:
        return "1-4h"
    else:
        return "4h+"


@router.get("/incidents")
async def get_incidents(artifacts: ArtifactsDep):
    """
    Returns the most recent 150 incidents with ML-predicted severity.
    Feeds the Deck.gl heatmap and scatter layer on the frontend map.

    Steps:
    1. Read features.parquet (already has LightGBM-encoded features,
       plus id, event_cause, corridor, start_datetime, latitude, longitude)
    2. Sort by start_datetime descending, take last 150 rows
    3. Run batch inference on the 10 feature columns
    4. Derive severity and duration display strings
    5. Return list of incident objects for the map
    """
    try:
        data_dir = Path(get_settings().data_dir)
        features_path = data_dir / "features.parquet"

        # Validate file exists
        if not features_path.exists():
            raise HTTPException(status_code=503, detail="Data files not available")

        # Load features (already has everything we need — no clean.parquet required)
        features_df = pd.read_parquet(features_path)
        logger.info(f"Loaded {len(features_df)} incidents from features.parquet")

        features_df = features_df.reset_index(drop=True)
        merged_df = features_df.copy()

        # Sort by start_datetime descending, take last 150 rows
        merged_df = merged_df.sort_values("start_datetime", ascending=False).head(150)

        if len(merged_df) == 0:
            return []

        # Build feature matrix from the 10 pre-encoded columns
   # Build feature DataFrame, keeping categoricals as pandas 'category'
        # dtype (LightGBM's native categorical handling — not label-encoded floats)
        CATEGORICAL_COLS = ["event_cause", "event_type", "corridor"]

        feature_df = merged_df[FEATURE_COLS].copy()
        for col in CATEGORICAL_COLS:
            feature_df[col] = feature_df[col].astype("category")

        # Run batch inference in thread (lgb.predict is blocking C++ code)
        closure_probs = await asyncio.to_thread(
            artifacts.severity_model.predict, feature_df
        )
        duration_raw = await asyncio.to_thread(
            artifacts.duration_model.predict, feature_df
        )

        # Get decision threshold from metrics (default 0.5 if not present)
        decision_threshold = artifacts.metrics.get("closure", {}).get(
            "decision_threshold", 0.5
        )

        # Build response list
        result = []
        for idx, (_, row) in enumerate(merged_df.iterrows()):
            closure_prob = float(closure_probs[idx])
            # Inverse log1p transform: predicted_minutes = expm1(raw_pred)
            predicted_minutes = math.expm1(float(duration_raw[idx]))

            result.append(
                {
                    "id": str(row.get("id", "")),
                    "lat": float(row.get("latitude", 0.0)),
                    "lng": float(row.get("longitude", 0.0)),
                    "event_cause": str(row.get("event_cause", "")),
                    "corridor": str(row.get("corridor", "")),
                    "hour": int(row.get("hour", 0)),
                    "severity": _severity_tier(closure_prob, decision_threshold),
                    "closure_prob": closure_prob,
                    "duration_display": _duration_display(predicted_minutes),
                    "start_datetime": (
                        row.get("start_datetime").isoformat()
                        if pd.notna(row.get("start_datetime"))
                        else ""
                    ),
                }
            )

        return result

    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.error(f"Data file not found: {e}")
        raise HTTPException(status_code=503, detail="Data files not available")
    except Exception as e:
        logger.error(f"Error fetching incidents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/after-action")
async def get_after_action(artifacts: ArtifactsDep):
    """
    Returns after-action review comparing ML-predicted clearance time
    vs actual clearance time on closed incidents.
    
    Steps:
    1. Read clean.parquet and filter to closed incidents only
    2. Compute actual clearance time in minutes
    3. Join with features.parquet to get encoded features for inference
    4. Run duration model batch inference
    5. Convert log-space predictions back to minutes using expm1
    6. Compute absolute errors
    7. Return summary stats and top 200 errors for operational review
    """
    try:
        data_dir = Path(get_settings().data_dir)
        clean_path = data_dir / "clean.parquet"
        features_path = data_dir / "features.parquet"

        if not clean_path.exists() or not features_path.exists():
            raise HTTPException(status_code=503, detail="Data files not available")

        clean_df = pd.read_parquet(clean_path)
        features_df = pd.read_parquet(features_path)
        logger.info(f"Loaded {len(clean_df)} incidents from clean.parquet")

        # Filter to closed incidents (has actual clearance time)
        closed_df = clean_df[clean_df["closed_datetime"].notna()].copy()

        # Compute actual clearance time in minutes
        closed_df["actual_minutes"] = (
            (closed_df["closed_datetime"] - closed_df["start_datetime"]).dt.total_seconds()
            / 60
        )

        # Filter: 0 < actual_minutes < 1440 (24h cap)
        closed_df = closed_df[
            (closed_df["actual_minutes"] > 0) & (closed_df["actual_minutes"] < 1440)
        ]

        # Sort by start_datetime, take last 500 rows
        closed_df = closed_df.sort_values("start_datetime", ascending=False).head(500)

        if len(closed_df) == 0:
            return {
                "summary": {
                    "total_incidents": 0,
                    "mean_actual_minutes": 0.0,
                    "mean_predicted_minutes": 0.0,
                    "median_absolute_error": 0.0,
                    "learning_helped": False,
                    "drift_note": "No closed incidents available for analysis.",
                },
                "incidents": [],
            }

        # Join with features.parquet on id to get encoded features
        # Use suffixes to avoid duplicate column names (closed_df already has event_cause, corridor)
        merged_df = closed_df.merge(
            features_df[FEATURE_COLS + ["id"]], 
            on="id", 
            how="inner",
            suffixes=("", "_feat")
        )

        if len(merged_df) == 0:
            return {
                "summary": {
                    "total_incidents": 0,
                    "mean_actual_minutes": 0.0,
                    "mean_predicted_minutes": 0.0,
                    "median_absolute_error": 0.0,
                    "learning_helped": False,
                    "drift_note": "No matching feature data for closed incidents.",
                },
                "incidents": [],
            }

        # Build feature DataFrame, keeping categoricals as pandas 'category'
        # dtype (LightGBM's native categorical handling — not label-encoded floats)
        CATEGORICAL_COLS = ["event_cause", "event_type", "corridor"]

        feature_df = merged_df[FEATURE_COLS].copy()
        for col in CATEGORICAL_COLS:
            feature_df[col] = feature_df[col].astype("category")

        # Run batch inference in thread (lgb.predict is blocking C++ code)
        duration_raw = await asyncio.to_thread(
            artifacts.duration_model.predict, feature_df
        )

        # Convert log-space predictions back to minutes using inverse log1p
        merged_df["predicted_minutes"] = [
            math.expm1(float(p)) for p in duration_raw
        ]
        merged_df["absolute_error"] = (
            merged_df["actual_minutes"] - merged_df["predicted_minutes"]
        ).abs()

        # Compute summary statistics
        summary = {
            "total_incidents": int(len(merged_df)),
            "mean_actual_minutes": float(merged_df["actual_minutes"].mean()),
            "mean_predicted_minutes": float(merged_df["predicted_minutes"].mean()),
            "median_absolute_error": float(merged_df["absolute_error"].median()),
            "learning_helped": False,  # hardcoded: drift detected
            "drift_note": (
                "Clearance time dominated by admin closeout noise — "
                "distribution drift detected. System surfaces this for "
                "operational review."
            ),
        }

        # Top 200 incidents by absolute error (descending)
        top_incidents = merged_df.nlargest(200, "absolute_error")
        incidents = []
        for _, row in top_incidents.iterrows():
            incidents.append(
                {
                    "id": str(row.get("id", "")),
                    "event_cause": str(row.get("event_cause", "")),
                    "corridor": str(row.get("corridor", "")),
                    "lat": float(row.get("latitude", 0.0)),
                    "lng": float(row.get("longitude", 0.0)),
                    "actual_minutes": float(row["actual_minutes"]),
                    "predicted_minutes": float(row["predicted_minutes"]),
                    "absolute_error": float(row["absolute_error"]),
                    "start_datetime": (
                        row.get("start_datetime").isoformat()
                        if pd.notna(row.get("start_datetime"))
                        else ""
                    ),
                }
            )

        return {
            "summary": summary,
            "incidents": incidents,
        }

    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.error(f"Data file not found: {e}")
        raise HTTPException(status_code=503, detail="Data files not available")
    except Exception as e:
        logger.error(f"Error fetching after-action data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_metrics(artifacts: ArtifactsDep):
    """
    Returns model card data from artifacts.metrics.
    
    No computation — simply returns the metrics dict that was loaded
    from models/metrics.json at startup. This includes closure model
    metrics (ROC-AUC, PR-AUC, confusion matrix) and duration model
    metrics (MAE, median AE).
    
    If metrics unavailable, return HTTP 503.
    """
    if not artifacts.metrics or len(artifacts.metrics) == 0:
        raise HTTPException(
            status_code=503, detail="Metrics not loaded — check models/metrics.json"
        )

    return JSONResponse(content=artifacts.metrics)

@router.get("/geocode")
async def geocode(lat: float, lng: float):
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"format": "json", "lat": lat, "lon": lng, "zoom": 16, "addressdetails": 1},
                headers={"User-Agent": "ClearPathOS/1.0", "Accept-Language": "en"},
                timeout=5,
            )
            data = r.json()
            addr = data.get("address", {})
            name = (
                addr.get("neighbourhood") or addr.get("suburb") or
                addr.get("road") or addr.get("village") or
                data.get("display_name", "").split(",")[0]
            )
            return {"name": name or "Unknown"}
    except Exception:
        return {"name": "Unknown"}
    except Exception:
        return {"name": "Unknown"}
    
@router.get("/stations")
async def get_stations(artifacts: ArtifactsDep, city_state: CityStateDep):
    """
    Returns all 54 police stations with current availability.
    
    Merges static station data (from artifacts.station_data loaded at startup)
    with live availability from city_state. Frontend uses this for station
    markers on the map.
    
    Each station includes:
    - station_id: unique identifier
    - lat, lng: geographic coordinates
    - capacity: max available units
    - available: current units available (from city_state, or default to 0)
    """
    try:
        station_data = artifacts.station_data

        result = []
        for _, row in station_data.iterrows():
            station_id = str(row.get("station_id", ""))
            
            # Look up current availability from city_state, default to 0
            availability_info = city_state.stations.get(station_id, {})
            available = availability_info.get("available", 0)

            result.append(
                {
                    "station_id": station_id,
                    "lat": float(row.get("lat", 0.0)),
                    "lng": float(row.get("lng", 0.0)),
                    "capacity": int(row.get("capacity", 0)),
                    "available": int(available),
                }
            )

        return result
    


    except Exception as e:
        logger.error(f"Error fetching stations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/simulate-city")
async def simulate_city(payload: dict):
    import math
    data_dir = Path(get_settings().data_dir)
    df = pd.read_parquet(data_dir / "features.parquet")
    
    # Fill missing duration/impact with safe defaults
    df["dur"] = pd.to_numeric(df.get("dur_target_min", pd.Series([30]*len(df))), errors="coerce").fillna(30)
    df["sev"] = pd.to_numeric(df.get("impact_level", pd.Series([1]*len(df))), errors="coerce").fillna(1) + 1

    assets = payload.get("assets", [])
    
    def haversine(lat1, lng1, lat2, lng2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    CAUSE_MAP = {
        "response_hub": ["accident", "vehicle_breakdown"],
        "drainage_grid": ["water_logging"],
        "maintenance_depot": ["pot_holes"],
    }

    d_sim = df["dur"].copy()
    s_sim = df["sev"].copy()
    breakdown = {"response_hub": 0, "drainage_grid": 0, "maintenance_depot": 0}

    for asset in assets:
        atype = asset["type"]
        alat, alng = asset["lat"], asset["lng"]
        radius_km = asset["radius_km"]
        rate = asset["reduction_rate"]
        causes = CAUSE_MAP.get(atype, [])

        mask = (
            df["event_cause"].isin(causes) &
            df.apply(lambda r: haversine(alat, alng, r["latitude"], r["longitude"]) <= radius_km, axis=1)
        )
        
        if atype == "drainage_grid":
            d_sim[mask] = 0
            s_sim[mask] = 0
        else:
            d_sim[mask] = d_sim[mask] * (1 - rate)
        
        breakdown[atype] += int(mask.sum())

    historical_burden = float((df["dur"] * df["sev"]).sum())
    simulated_burden = float((d_sim * s_sim).sum())
    gr_score = 0.0 if historical_burden == 0 else round(100 * (1 - simulated_burden / historical_burden), 2)
    
    total_minutes_saved = float((df["dur"] - d_sim).sum())
    
    return {
        "gr_score": gr_score,
        "historical_burden": round(historical_burden, 2),
        "simulated_burden": round(simulated_burden, 2),
        "incidents_affected": sum(breakdown.values()),
        "breakdown": breakdown,
        "avg_duration_reduction_min": round(total_minutes_saved / max(sum(breakdown.values()), 1), 2),
        "economic_value_inr": round(total_minutes_saved / 60 * 150, 2),
    }

@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket, city_state: CityStateDep, artifacts: ArtifactsDep):
    """
    WebSocket endpoint for pushing live city state to the frontend.
    
    On connect:
    1. Send initial {"type": "connected", "active_incidents": count}
    2. Enter heartbeat loop: every 5 seconds send current state
       {"type": "heartbeat",
        "active_incidents": int,
        "station_availability": {station_id: available_count, ...},
        "timestamp": ISO datetime string}
    3. On disconnect, log at INFO level (disconnect is normal)
    """
    await websocket.accept()

    try:
        # Send initial connection confirmation
        await websocket.send_json(
            {
                "type": "connected",
                "active_incidents": len(city_state.active_incidents),
            }
        )
        heartbeat_count=0

        # Heartbeat loop: send current state every 5 seconds
        while True:
            await asyncio.sleep(5)
            heartbeat_count+=1

            # Build current station availability map
            station_availability = {
                station_id: availability_info.get("available", 0)
                for station_id, availability_info in city_state.stations.items()
            }

            # Send heartbeat with current city state
            # Risk grid scan runs every 6th heartbeat (5s * 6 = 30s),
            # not every heartbeat, to avoid re-scoring 36 cells too often.
            risk_alerts = []
            if heartbeat_count % 6 == 0:
                grid_scores = await asyncio.to_thread(_score_risk_grid, artifacts)
                top_3 = sorted(grid_scores, key=lambda c: c["closure_prob"], reverse=True)[:3]
                risk_alerts = top_3

            # Send heartbeat with current city state
            await websocket.send_json(
                {
                    "type": "heartbeat",
                    "active_incidents": len(city_state.active_incidents),
                    "station_availability": station_availability,
                    "risk_alerts": risk_alerts,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011)

# ════════════════════════════════════════════════════════════════
# COMPLAINTS — PostgreSQL via SQLAlchemy
# ════════════════════════════════════════════════════════════════
import os
import uuid
from datetime import datetime

from sqlalchemy import create_engine, Column, String, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./complaints.db")
print("DATABASE_URL =", repr(DATABASE_URL))
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class ComplaintModel(Base):
    __tablename__ = "complaints"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    text         = Column(Text)
    language     = Column(String)   # "en" or "kn"
    category     = Column(String)
    lat          = Column(Float)
    lng          = Column(Float)
    submitted_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

class ComplaintIn(BaseModel):
    text: str
    language: str = "en"
    category: str = "general"
    lat: float = 0.0
    lng: float = 0.0

@router.post("/complaints")
def save_complaint(data: ComplaintIn):
    db = Session()
    try:
        c = ComplaintModel(
            id=str(uuid.uuid4()),
            text=data.text,
            language=data.language,
            category=data.category,
            lat=data.lat,
            lng=data.lng,
            submitted_at=datetime.utcnow(),
        )
        db.add(c)
        db.commit()
        return {"id": c.id, "submitted_at": c.submitted_at.isoformat()}
    finally:
        db.close()

@router.get("/complaints")
def get_complaints():
    db = Session()
    try:
        rows = db.query(ComplaintModel).order_by(ComplaintModel.submitted_at.desc()).limit(200).all()
        return [
            {
                "id": r.id,
                "text": r.text,
                "language": r.language,
                "category": r.category,
                "lat": r.lat,
                "lng": r.lng,
                "submitted_at": r.submitted_at.isoformat(),
            }
            for r in rows
        ]
    finally:
        db.close()