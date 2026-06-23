# Dependencies (Model loaders, state access)
"""
Dependency injection layer for ClearPath OS.

Exposes ModelArtifacts and CityState from app.state via FastAPI Depends().

This file contains ZERO business logic. It only reads from app.state
(initialized by lifespan in main.py) and raises 503 if not present.

WHY Depends() over global variables:
────────────────────────────────────
- Globals are invisible to FastAPI's dependency graph — untestable,
  unoverridable, undocumented in OpenAPI schema.
- Depends() makes dependencies explicit in function signatures.
- In tests: override with app.dependency_overrides[fn] = mock.
- In production: resolved once per request from app.state.

WHY app.state over lru_cache:
──────────────────────────────
- CityState is mutable — it changes every time a plan is committed
  (officers decremented, incidents added, load updated).
- lru_cache would freeze the initial empty state forever, making all
  city state mutations invisible to subsequent requests.
- app.state is the correct FastAPI idiom for lifespan-scoped shared
  mutable objects.
"""

from typing import Annotated,TypeAlias

from fastapi import Depends, HTTPException, Request
from fastapi import Request, WebSocket
from app.core.state import ModelArtifacts, CityState


async def get_model_artifacts(
    request: Request = None, websocket: WebSocket = None
) -> ModelArtifacts:
    """
    Retrieve preloaded ML models from app.state.

    Called by FastAPI dependency resolution on every request that
    declares artifacts as a parameter. The Request object grants
    access to request.app.state, where lifespan stored the artifacts.

    Returns:
        ModelArtifacts with LightGBM severity/duration models,
        NetworkX road graph, and station data loaded at startup.

    Raises:
        HTTPException(503): If artifacts not loaded during startup
                           (indicates lifespan failed silently).
    """
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
    """
    Retrieve live city operational state from app.state.

    Called by FastAPI dependency resolution on every request that
    declares city_state as a parameter. The state is mutable — it
    changes every time a plan is committed to reflect resource
    depletion and incident tracking.

    Works for both HTTP routes (request) and WebSocket routes
    (websocket) since only one of the two will be non-None depending
    on the connection type.

    Returns:
        CityState with active incidents, station availability,
        and corridor load initialized at startup.

    Raises:
        HTTPException(503): If city state not initialized during startup
                           (indicates lifespan failed silently). Only
                           raised for HTTP routes — WebSocket routes
                           get None back and should handle it themselves.
    """
    conn = request or websocket
    city_state = getattr(conn.app.state, "city_state", None)

    if city_state is None:
        if request is not None:
            raise HTTPException(
                status_code=503,
                detail="City state not initialized. Run lifespan startup.",
            )
        # For websocket routes, raising HTTPException won't behave
        # correctly mid-handshake — let the caller decide what to do.
        return None

    return city_state
# ════════════════════════════════════════════════════════════════════════════
# TYPED DEPENDENCY ALIASES (modern FastAPI pattern, 0.95+)
# ════════════════════════════════════════════════════════════════════════════

ArtifactsDep: TypeAlias = Annotated[ModelArtifacts, Depends(get_model_artifacts)]
"""
Typed dependency alias for ModelArtifacts.

Use in endpoint signatures:
    @app.post("/api/plan")
    async def create_plan(artifacts: ArtifactsDep) -> ...:
        ...

Instead of:
    async def create_plan(
        artifacts: ModelArtifacts = Depends(get_model_artifacts)
    ) -> ...:
        ...

Cleaner, more readable, and eliminates repetition.
"""

CityStateDep: TypeAlias = Annotated[CityState, Depends(get_city_state)]
"""
Typed dependency alias for CityState.

Use in endpoint signatures:
    @app.post("/api/plan")
    async def create_plan(city_state: CityStateDep) -> ...:
        ...

Cleaner than inline Depends() in every endpoint.
"""