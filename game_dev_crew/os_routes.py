"""AgentOS extras: full ``GET /components`` listing and ``GET /system/db-components``."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Optional

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


def _list_components_slice(
    db: BaseDb,
    *,
    component_type: Optional[DbComponentType],
    page: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int, float]:
    offset = (page - 1) * limit
    t0 = time.time() * 1000
    rows, total_count = db.list_components(
        component_type=component_type,
        limit=limit,
        offset=offset,
        exclude_component_ids=None,
    )
    return rows, total_count, round(time.time() * 1000 - t0, 2)


def patch_agentos_components_list(app: "FastAPI", db: BaseDb) -> None:
    """Swap AgentOS ``GET /components`` so SQLite lists registry agents and teams too."""
    settings = AgnoAPISettings()
    kept: list[Any] = []
    for route in app.router.routes:
        if (
            isinstance(route, APIRoute)
            and route.name == "list_components"
            and route.path == "/components"
            and "GET" in route.methods
        ):
            continue
        kept.append(route)
    if len(kept) == len(app.router.routes):
        return

    app.router.routes = kept

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
        description="Paginated rows from ``agno_components`` (agents, teams, workflows).",
    )
    async def list_components(
        component_type: Optional[ComponentType] = Query(
            None, description="Filter by type: agent, team, workflow"
        ),
        page: int = Query(1, ge=1, description="Page number"),
        limit: int = Query(20, ge=1, le=100, description="Items per page"),
    ) -> PaginatedResponse[ComponentResponse]:
        try:
            ct = DbComponentType(component_type.value) if component_type else None
            components, total_count, search_ms = _list_components_slice(
                db, component_type=ct, page=page, limit=limit
            )
            total_pages = (total_count + limit - 1) // limit if limit > 0 else 0
            return PaginatedResponse(
                data=[ComponentResponse(**c) for c in components],
                meta=PaginationInfo(
                    page=page,
                    limit=limit,
                    total_pages=total_pages,
                    total_count=total_count,
                    search_time_ms=search_ms,
                ),
            )
        except Exception as e:
            log_error(f"Error listing components: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

    app.include_router(router)


def attach_system_components_routes(app: "FastAPI") -> None:
    router = APIRouter(prefix="/system", tags=["System"])

    @router.get(
        "/db-components",
        summary="List agno_components",
        description="Same shape as ``GET /components`` on this server; no auth dependency.",
    )
    def list_db_components(
        component_type: Optional[str] = Query(None, description="Filter: agent, team, or workflow"),
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
    ) -> dict[str, Any]:
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

        rows, total_count, search_ms = _list_components_slice(
            db, component_type=ct, page=page, limit=limit
        )
        total_pages = (total_count + limit - 1) // limit if limit else 0
        return {
            "data": rows,
            "meta": {
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "total_count": total_count,
                "search_time_ms": search_ms,
            },
        }

    app.include_router(router)
