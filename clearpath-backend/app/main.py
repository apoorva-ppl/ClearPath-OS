# App Lifespan & Middleware
"""
FastAPI application entry point for ClearPath OS.

Owns exactly two responsibilities:
1. Lifespan — load heavy artifacts ONCE at startup
2. App assembly — register middleware, routers, SSE endpoint

Zero business logic here. No agent calls, inference, or graph construction.

WHY LIFESPAN over @app.on_event("startup"):
────────────────────────────────────────────
- on_event deprecated since FastAPI 0.93.
- lifespan = single context manager, startup/shutdown colocated.
- Artifacts in app.state, not globals, so tests can override directly.

WHY MODELS LOADED IN LIFESPAN, NOT ENDPOINT:
──────────────────────────────────────────
- LightGBM + NetworkX graphml take 800ms-2s to load.
- Per-request loading = 2s stall before first SSE byte.
- Lifespan loads once → <10ms endpoint latency to first byte.

WHY SSE OVER WEBSOCKET:
───────────────────────
- SSE = strictly server→client. No handshake. HTTP/2 compatible.
- WebSocket = bidirectional overkill for read-only progress stream.
- Request-response returns nothing until pipeline finishes (~2s).
- SSE returns each agent result as it completes — feels instant.

WHY GZIP ON SSE STREAM:
──────────────────────
- SSE sends repeated JSON deltas. JSON compresses 70-80%.
- On 4G: difference between smooth animation and choppy updates.
- GZip transparent to browser EventSource API.
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi.staticfiles import StaticFiles

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse, Response

from app.core.config import get_settings
from app.core.state import ModelArtifacts, CityState, IncidentInput
from app.core.generator import stream_incident_plan
from app.api.deps import ArtifactsDep, CityStateDep


# ════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("clearpath.main")


# ════════════════════════════════════════════════════════════════════════════
# LIFESPAN CONTEXT MANAGER
# ════════════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan: startup and shutdown.

    Startup (before yield):
      1. Load artifacts in thread pool (blocking I/O).
      2. Initialize city state from station data.
      3. Create audio output directory for synthesized dispatches.
      4. Store both on app.state for request-scoped access.

    Shutdown (after yield):
      5. Log graceful shutdown. No explicit cleanup needed
         (GC handles LightGBM/NetworkX cleanup).
    """
    settings = get_settings()
    log.info("ClearPath OS starting up...")

    # Load models in thread pool (blocking C++/I/O code)
    artifacts = await asyncio.to_thread(_load_artifacts, settings)
    app.state.artifacts = artifacts
    log.info(
        "Artifacts loaded",
        extra={
            "severity_model": str(Path(settings.model_dir) / "severity.txt"),
            "duration_model": str(Path(settings.model_dir) / "duration.txt"),
            "graph_nodes": len(artifacts.road_graph),
            "stations": len(artifacts.station_data),
        },
    )

    # Initialize city state
    city_state = _init_city_state(artifacts.station_data, settings)
    app.state.city_state = city_state
    log.info("City state initialized", extra={"stations": len(city_state.stations)})

    # Create audio output directory
# Create audio output directory
    audio_dir = Path(settings.audio_dir)
    if not audio_dir.is_absolute():
        audio_dir = Path(__file__).parent.parent / audio_dir
    audio_dir.mkdir(parents=True, exist_ok=True)
    log.info("Audio output directory created", extra={"path": str(audio_dir)})

    yield  # ← Server runs here

    log.info("ClearPath OS shutting down cleanly")


# ════════════════════════════════════════════════════════════════════════════
# LIFESPAN HELPERS
# ════════════════════════════════════════════════════════════════════════════


def _load_artifacts(settings) -> ModelArtifacts:
    """
    Load all ML models, graph, and station data from disk (sync).

    WHY asyncio.to_thread():
      - LightGBM Booster loading and NetworkX graphml parsing are
        blocking and CPU/IO bound (C++ code under the hood).
      - Calling directly in async startup() blocks the event loop.
      - asyncio.to_thread() runs them in threadpool — event loop
        stays responsive during startup.

    WHY RuntimeError on missing models:
      - Missing severity.txt or duration.txt = broken system, not
        degraded. ML inference is the first agent and non-optional.
      - Crash fast with a clear message so ops knows what happened.

    WHY warning (not error) on missing graph:
      - Synthetic grid is valid for demo/dev (no real OSM data).
      - Fallback allows standalone testing without OSM data.
      - Production should fail if graph is missing (validate in config).

    Args:
        settings: Application settings with paths and configs.

    Returns:
        ModelArtifacts with loaded models, graph, station data.

    Raises:
        RuntimeError: If severity.txt or duration.txt not found.
    """
    import lightgbm as lgb
    import networkx as nx
    import pandas as pd

    model_dir = Path(settings.model_dir)
    data_dir = Path(settings.data_dir)

    # Load LightGBM models (required)
    severity_path = model_dir / "severity.txt"
    duration_path = model_dir / "duration.txt"
    if not severity_path.exists() or not duration_path.exists():
        raise RuntimeError(
            f"Missing LightGBM models:\n"
            f"  {severity_path}\n"
            f"  {duration_path}\n"
            f"Run: python run_pipeline.py"
        )

    severity_model = lgb.Booster(model_file=str(severity_path))
    duration_model = lgb.Booster(model_file=str(duration_path))

    # Load NetworkX graph (optional, synthetic fallback)
    # road_graph is used consistently throughout — no alias switching
    graph_path = model_dir / "bengaluru.graphml"
    if graph_path.exists():
        road_graph = nx.read_graphml(graph_path)
    else:
        log.warning(
            "Road graph not found, using synthetic grid",
            extra={"expected": str(graph_path)},
        )
        # BUG FIX: was `graph = ...` (wrong name), return used `road_graph`
        road_graph = nx.grid_2d_graph(10, 10)

    # Load station data and metrics
    stations_path = data_dir / "stations.csv"
    station_data = pd.read_csv(stations_path)

    metrics_path = model_dir / "metrics.json"
    with open(metrics_path) as f:
        metrics = json.load(f)

    # BUG FIX: was road_graph=graph (undefined), now road_graph=road_graph
    return ModelArtifacts(
        severity_model=severity_model,
        duration_model=duration_model,
        road_graph=road_graph,
        station_data=station_data,
        metrics=metrics,
    )


def _init_city_state(station_data, settings) -> CityState:
    """
    Initialize CityState from station data (pure function).

    Builds station availability map and initializes empty incident list.

    Args:
        station_data: pd.DataFrame with columns [station_id, capacity, lat, lng].
        settings: Application settings with default capacity value.

    Returns:
        CityState with initialized stations and empty incidents.
    """
    stations_dict = {}
    for _, row in station_data.iterrows():
        station_id = str(row["station_id"])
        capacity = int(row.get("capacity", settings.station_capacity))
        stations_dict[station_id] = {
            "name": row.get("name", station_id),  # fallback to id if no name col
            "capacity": capacity,
            "available": capacity,
            "lat": float(row.get("lat", 0.0)),
            "lng": float(row.get("lng", 0.0)),
        }

    return CityState(
        stations=stations_dict,
        active_incidents={},
    )


# ════════════════════════════════════════════════════════════════════════════
# FASTAPI APP INITIALIZATION
# ════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="ClearPath OS — Autonomous Traffic Command Center",
    version="1.0.0",
    description="ML + OR prediction pipeline for Bengaluru traffic police",
    lifespan=lifespan,
)

# Middleware registration (order matters in Starlette)
# GZip before CORS so compression applies to all responses including preflight
settings = get_settings()
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    # TODO: restrict origins in production deployment
)

# Mount static files for synthesized dispatch audio
audio_dir_path = Path(settings.audio_dir)
if not audio_dir_path.is_absolute():
    audio_dir_path = Path(__file__).parent.parent / audio_dir_path
app.mount("/audio", StaticFiles(directory=str(audio_dir_path)), name="audio")

# ════════════════════════════════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════════════════════════════════


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check for load balancers and monitoring."""
    return {"status": "ok", "service": "clearpath-os"}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.post("/api/plan/stream")
async def plan_stream(
    incident: IncidentInput,
    artifacts: ArtifactsDep,
    city_state: CityStateDep,
) -> StreamingResponse:
    """
    Stream a disaster response plan via SSE.

    Orchestrates incident through 4-agent pipeline, streaming live
    updates as each agent completes. Total latency ~2-10s depending
    on supervisor loop iterations and network conditions.

    WHY StreamingResponse not JSONResponse:
      - Pipeline takes ~2s. JSONResponse would stall 2s with blank
        screen. SSE returns each agent result (~200ms intervals) so
        frontend animates progress immediately.

    WHY X-Accel-Buffering header:
      - Nginx buffers responses by default. Without this header,
        nginx holds all SSE chunks until buffer fills, breaking
        real-time streaming entirely.

    WHY GeneratorExit caught silently:
      - Client disconnect mid-stream is normal (user closes browser,
        network flickers). Not an error condition — log at INFO,
        no traceback.

    Args:
        incident: Raw incident input (location, cause, priority).
        artifacts: Preloaded ML models (LightGBM, NetworkX, etc.).
        city_state: Live city operational state (mutable).

    Returns:
        StreamingResponse with text/event-stream content type.
        Each SSE event: data: {"step": "...", ...}\n\n
    """
    generator = stream_incident_plan(incident, artifacts, city_state)
    wrapped = _sse_wrap(generator)

    return StreamingResponse(
        wrapped,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


async def _sse_wrap(
    gen: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    """
    Wrap a string generator with SSE formatting.

    Each yielded string becomes: data: {string}\n\n
    Handles client disconnect (GeneratorExit) silently.
    Re-raises other exceptions after yielding error event.

    Args:
        gen: Async generator yielding JSON strings from pipeline.

    Yields:
        SSE-formatted lines ready for browser EventSource consumption.
    """
    try:
        async for chunk in gen:
            yield f"data: {chunk}\n\n"
    except GeneratorExit:
        log.info("SSE client disconnected mid-stream")
    except Exception as err:
        log.exception(f"SSE stream error: {err}")
        error_event = json.dumps({
            "step": "error",
            "status": "error",
            "message": str(err),
            "state": None,
        })
        yield f"data: {error_event}\n\n"
        raise


# ════════════════════════════════════════════════════════════════════════════
# ADDITIONAL ROUTES
# ════════════════════════════════════════════════════════════════════════════

try:
    from app.api.endpoints import router as api_router
    app.include_router(api_router, prefix="/api")
    # Serve the frontend map UI as static files — MUST be mounted last,
    # after all API routes, since a "/" mount with html=True acts as a
    # catch-all and would otherwise shadow /health, /api/*, etc.
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)

# Only mount frontend if index.html exists (skip on Render where frontend is on Vercel)
    if (frontend_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    else:
        log.info("No frontend build found — skipping static mount (frontend served by Vercel)")
except ImportError:
    log.warning("API endpoints router not found; skipping registration")
# ════════════════════════════════════════════════════════════════════════════
# UVICORN ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )