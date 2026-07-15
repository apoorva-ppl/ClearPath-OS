from typing import Annotated,TypeAlias
from fastapi import Depends, HTTPException, Request
from fastapi import Request, WebSocket
from app.core.state import ModelArtifacts, CityState


async def get_model_artifacts(
    request: Request = None, websocket: WebSocket = None
) -> ModelArtifacts:
    conn = request or websocket
    artifacts = getattr(conn.app.state, "artifacts", None)
    if artifacts is None:
        if request is not None:
            raise HTTPException(
                status_code=503,
                detail="Model artifacts not loaded. Run lifespan startup.",
            )
        return None
    return artifacts


async def get_city_state(
    request: Request = None, websocket: WebSocket = None
) -> CityState:
    conn = request or websocket
    city_state = getattr(conn.app.state, "city_state", None)

    if city_state is None:
        if request is not None:
            raise HTTPException(
                status_code=503,
                detail="City state not initialized. Run lifespan startup.",
            )
        return None

    return city_state

ArtifactsDep: TypeAlias = Annotated[ModelArtifacts, Depends(get_model_artifacts)]

CityStateDep: TypeAlias = Annotated[CityState, Depends(get_city_state)]
