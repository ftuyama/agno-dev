"""Routes to list ``agno_components`` as stored in SQLite.

Upstream AgentOS ``GET /components`` excludes component IDs owned by the in-process ``Registry``
(code-defined agents and teams). This app **replaces** that handler so ``GET /components`` lists
every row in ``agno_components`` (agents, teams, workflows), matching Studio expectations.

``GET /system/db-components`` remains as an explicit debug alias (same query params, no auth quirks).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from agno.db.base import BaseDb, ComponentType as DbComponentType
from agno.os.auth import get_authentication_dependency
from agno.os.schema import (
    BadRequestResponse,
    ComponentResponse,
    ComponentType,
    InternalServerErrorResponse,
    NotFoundResponse,
    PaginatedResponse,
    PaginationInfo,
    UnauthenticatedResponse,
    ValidationErrorResponse,
)
from agno.os.settings import AgnoAPISettings
from agno.utils.log import log_error
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.routing import APIRoute

from game_dev_crew.config import load_env, make_agent_db

if TYPE_CHECKING:
    from fastapi import FastAPI


def replace_agentos_components_list_route(app: "FastAPI", db: BaseDb) -> None:
    """Swap AgentOS ``list_components`` for one that does not exclude registry-backed IDs."""
    settings = AgnoAPISettings()
    new_routes: list = []
    removed = False
    for route in app.router.routes:
        if (
            isinstance(route, APIRoute)
            and route.name == "list_components"
            and route.path == "/components"
            and "GET" in route.methods
        ):
            removed = True
            continue
        new_routes.append(route)
    if not removed:
        return

    app.router.routes = new_routes

    router = APIRouter(
        dependencies=[Depends(get_authentication_dependency(settings))],
        tags=["Components"],
        responses={
            400: {"description": "Bad Request", "model": BadRequestResponse},
            401: {"description": "Unauthorized", "model": UnauthenticatedResponse},
            404: {"description": "Not Found", "model": NotFoundResponse},
            422: {"description": "Validation Error", "model": ValidationErrorResponse},
            500: {"description": "Internal Server Error", "model": InternalServerErrorResponse},
        },
    )

    @router.get(
        "/components",
        response_model=PaginatedResponse[ComponentResponse],
        response_model_exclude_none=True,
        status_code=200,
        name="list_components",
        operation_id="list_components",
        summary="List Components",
        description=(
            "Paginated components from SQLite, including code-defined agents and teams "
            "(no registry ID exclusion)."
        ),
    )
    async def list_components(
        component_type: Optional[ComponentType] = Query(
            None, description="Filter by type: agent, team, workflow"
        ),
        page: int = Query(1, ge=1, description="Page number"),
        limit: int = Query(20, ge=1, le=100, description="Items per page"),
    ) -> PaginatedResponse[ComponentResponse]:
        try:
            start_time_ms = time.time() * 1000
            offset = (page - 1) * limit
            components, total_count = db.list_components(
                component_type=DbComponentType(component_type.value) if component_type else None,
                limit=limit,
                offset=offset,
                exclude_component_ids=None,
            )
            total_pages = (total_count + limit - 1) // limit if limit > 0 else 0
            return PaginatedResponse(
                data=[ComponentResponse(**c) for c in components],
                meta=PaginationInfo(
                    page=page,
                    limit=limit,
                    total_pages=total_pages,
                    total_count=total_count,
                    search_time_ms=round(time.time() * 1000 - start_time_ms, 2),
                ),
            )
        except Exception as e:
            log_error(f"Error listing components: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

    app.include_router(router)


def attach_raw_db_components_routes(app: "FastAPI") -> None:
    router = APIRouter(prefix="/system", tags=["Database (debug)"])

    @router.get(
        "/db-components",
        summary="List SQLite agno_components (debug alias)",
        description=(
            "Same pagination and rows as ``GET /components`` on this server (all agent/team/workflow "
            "rows in ``agno_components``). Unauthenticated; use for quick DB inspection."
        ),
    )
    def list_db_components(
        component_type: Optional[str] = Query(
            None,
            description="Filter: agent, team, or workflow",
        ),
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
    ) -> dict:
        load_env()
        db = make_agent_db()
        if db is None or not isinstance(db, BaseDb):
            return {
                "data": [],
                "meta": {
                    "page": page,
                    "limit": limit,
                    "total_pages": 0,
                    "total_count": 0,
                    "note": "SQLite / BaseDb disabled (AGNO_MEMORY_DB=none)",
                },
            }

        ct: Optional[DbComponentType] = None
        if component_type:
            try:
                ct = DbComponentType(component_type.strip().lower())
            except ValueError as e:
                raise HTTPException(
                    status_code=422,
                    detail="component_type must be agent, team, or workflow",
                ) from e

        offset = (page - 1) * limit
        t0 = time.time() * 1000
        rows, total_count = db.list_components(
            component_type=ct,
            limit=limit,
            offset=offset,
            exclude_component_ids=None,
        )
        total_pages = (total_count + limit - 1) // limit if limit else 0
        return {
            "data": rows,
            "meta": {
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "total_count": total_count,
                "search_time_ms": round(time.time() * 1000 - t0, 2),
            },
        }

    app.include_router(router)
