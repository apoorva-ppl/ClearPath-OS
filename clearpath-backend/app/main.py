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

#login setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("clearpath.main")

#lifespan:- runs once(loads ml model s, road graph , station data , city data)
#avoids loading model for every requests 
#reduces api latency 
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    log.info("ClearPath OS starting up...")


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

    city_state = _init_city_state(artifacts.station_data, settings)
    app.state.city_state = city_state
    log.info("City state initialized", extra={"stations": len(city_state.stations)})

# Create audio output directory
    audio_dir = Path(settings.audio_dir)
    if not audio_dir.is_absolute():
        audio_dir = Path(__file__).parent.parent / audio_dir
    audio_dir.mkdir(parents=True, exist_ok=True)
    log.info("Audio output directory created", extra={"path": str(audio_dir)})

    yield  # ← Server runs here

    log.info("ClearPath OS shutting down cleanly")

    # loads all heavy resources(lightGBM model, networkX graph , Station CSV ,metrics)
def _load_artifacts(settings) -> ModelArtifacts:
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


    graph_path = model_dir / "bengaluru.graphml"
    if graph_path.exists():
        road_graph = nx.read_graphml(graph_path)
    else:
        log.warning(
            "Road graph not found, using synthetic grid",
            extra={"expected": str(graph_path)},
        )
        road_graph = nx.grid_2d_graph(10, 10)

    # Load station data and metrics
    stations_path = data_dir / "stations.csv"
    station_data = pd.read_csv(stations_path)

    metrics_path = model_dir / "metrics.json"
    with open(metrics_path) as f:
        metrics = json.load(f)

    return ModelArtifacts(
        severity_model=severity_model,
        duration_model=duration_model,
        road_graph=road_graph,
        station_data=station_data,
        metrics=metrics,
    )


    # creates live city state(statiosn , avail officers ,active incidents)
def _init_city_state(station_data, settings) -> CityState:
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
#creates application(lifespan , metadata , versions)
app = FastAPI(
    title="ClearPath OS — Autonomous Traffic Command Center",
    version="1.0.0",
    description="ML + OR prediction pipeline for Bengaluru traffic police",
    lifespan=lifespan,
)

#middleware(GZip)
#compresses responses for faster network transfer
settings = get_settings()
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://clear-path-os.vercel.app",
        "https://clear-path-hnvi346v1-apoorva-pandeys-projects-14145643.vercel.app",
        "http://localhost:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for synthesized dispatch audio
audio_dir_path = Path(settings.audio_dir)
if not audio_dir_path.is_absolute():
    audio_dir_path = Path(__file__).parent.parent / audio_dir_path
app.mount("/audio", StaticFiles(directory=str(audio_dir_path)), name="audio")

#routes

@app.get("/health")
async def health() -> dict[str, str]:
    """Health check for load balancers and monitoring."""
    return {"status": "ok", "service": "clearpath-os"}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

#checks if server is alive 
@app.post("/api/plan/stream")
async def plan_stream(
    incident: IncidentInput,
    artifacts: ArtifactsDep,
    city_state: CityStateDep,
) -> StreamingResponse:
    generator = stream_incident_plan(incident, artifacts, city_state)
    wrapped = _sse_wrap(generator)

#main endpoint
    return StreamingResponse(
        wrapped,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )

#converts generator output to SSE(server sent events)
#frontend recieves them n update
async def _sse_wrap(
    gen: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
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

#additional routes
try:
    from app.api.endpoints import router as api_router
    app.include_router(api_router, prefix="/api")
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)

# Only mount frontend if index.html exists (skip on Render where frontend is on Vercel)
    if (frontend_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    else:
        log.info("No frontend build found — skipping static mount (frontend served by Vercel)")
except ImportError:
    log.warning("API endpoints router not found; skipping registration")


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