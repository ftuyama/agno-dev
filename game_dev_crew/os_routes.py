"""AgentOS extras: full ``GET /components`` listing and ``GET /system/db-components``."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, List, Optional

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
    WorkflowSummaryResponse,
)
from agno.os.settings import AgnoAPISettings
from agno.utils.log import log_error
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.routing import APIRoute
from urllib.parse import urlencode

from game_dev_crew.config import load_env, make_agent_db

if TYPE_CHECKING:
    from fastapi import FastAPI


def attach_registry_query_normalize(app: "FastAPI") -> None:
    """Normalize ``resource_type`` on ``GET /registry`` so bad clients still validate.

    Agno expects lowercase enum values (``tool``, ``model``, ``db``, …). A trailing
    comma (e.g. ``resource_type=model,``) or uppercase (``MODEL``) yields 422 and
    looks like an empty API in some clients.
    """

    @app.middleware("http")
    async def _normalize_registry_resource_type(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method != "GET":
            return await call_next(request)
        path = request.url.path.rstrip("/") or "/"
        if path != "/registry":
            return await call_next(request)
        raw = request.query_params.get("resource_type")
        if raw is None:
            return await call_next(request)
        fixed = raw.strip().rstrip(",").lower()
        if fixed == raw:
            return await call_next(request)
        request.scope["query_string"] = urlencode(
            [(k, fixed if k == "resource_type" else v) for k, v in request.query_params.multi_items()]
        ).encode("utf-8")
        return await call_next(request)


def _merge_db_workflow_rows_into_summaries(
    agent_os: Any,
    summaries: List[WorkflowSummaryResponse],
) -> List[WorkflowSummaryResponse]:
    """Load DB-backed workflows and merge into summaries (sync; safe for ``asyncio.to_thread``)."""
    from agno.workflow.workflow import get_workflows as load_workflows_from_db

    out = list(summaries)
    id_to_index: dict[str, int] = {}
    for i, row in enumerate(out):
        if row.id:
            id_to_index[row.id] = i

    if not (agent_os.db and isinstance(agent_os.db, BaseDb)):
        return out

    for db_workflow in load_workflows_from_db(db=agent_os.db, registry=agent_os.registry):
        wid = getattr(db_workflow, "id", None) or ""
        try:
            if wid and wid in id_to_index:
                idx = id_to_index[wid]
                base = out[idx]
                v = getattr(db_workflow, "_version", None)
                s = getattr(db_workflow, "_stage", None)
                db_id = db_workflow.db.id if db_workflow.db else None
                out[idx] = base.model_copy(
                    update={
                        "db_id": db_id or base.db_id,
                        "current_version": v if v is not None else base.current_version,
                        "stage": s if s is not None else base.stage,
                    }
                )
                continue
            out.append(WorkflowSummaryResponse.from_workflow(workflow=db_workflow, is_component=True))
        except Exception as exc:
            log_error(f"Error converting workflow {wid or 'unknown'} to response: {exc}")
            continue

    return out


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
            components, total_count, search_ms = await asyncio.to_thread(
                _list_components_slice,
                db,
                component_type=ct,
                page=page,
                limit=limit,
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


def patch_agentos_workflows_list(app: "FastAPI", agent_os: Any) -> None:
    """Replace AgentOS ``GET /workflows`` so DB-synced workflows are not listed twice.

    Upstream Agno appends every row from ``get_workflows(db=...)`` after ``os.workflows``.
    This project persists the same workflow definitions to SQLite (Studio / sync-components),
    so clients saw duplicate ids. We skip DB entries whose id is already on the OS instance
    and copy ``current_version`` / ``stage`` from the DB object onto the in-memory summary.
    """
    kept: list[Any] = []
    for route in app.router.routes:
        if (
            isinstance(route, APIRoute)
            and route.name == "get_workflows"
            and route.path == "/workflows"
            and route.methods is not None
            and "GET" in route.methods
        ):
            continue
        kept.append(route)
    if len(kept) == len(app.router.routes):
        return

    app.router.routes = kept
    settings = AgnoAPISettings()

    router = APIRouter(
        dependencies=[Depends(get_authentication_dependency(settings))],
        tags=["Workflows"],
        responses={
            400: {"description": "Bad Request", "model": BadRequestResponse},
            401: {"description": "Unauthorized", "model": UnauthenticatedResponse},
            404: {"description": "Not Found", "model": NotFoundResponse},
            422: {"description": "Validation Error", "model": ValidationErrorResponse},
            500: {"description": "Internal Server Error", "model": InternalServerErrorResponse},
        },
    )

    @router.get(
        "/workflows",
        response_model=List[WorkflowSummaryResponse],
        response_model_exclude_none=True,
        name="get_workflows",
        operation_id="get_workflows",
        summary="List All Workflows",
    )
    async def get_workflows(request: Request) -> List[WorkflowSummaryResponse]:
        if getattr(request.state, "authorization_enabled", False):
            from agno.os.auth import filter_resources_by_access, get_accessible_resources

            accessible_ids = get_accessible_resources(request, "workflows")
            if not accessible_ids:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            accessible_workflows = filter_resources_by_access(request, agent_os.workflows or [], "workflows")
        else:
            accessible_workflows = agent_os.workflows or []

        summaries: List[WorkflowSummaryResponse] = []
        if accessible_workflows:
            for workflow in accessible_workflows:
                row = WorkflowSummaryResponse.from_workflow(workflow=workflow, is_component=False)
                summaries.append(row)

        if agent_os.db and isinstance(agent_os.db, BaseDb):
            summaries = await asyncio.to_thread(_merge_db_workflow_rows_into_summaries, agent_os, summaries)

        return summaries

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
