"""AgentOS FastAPI app: exposes Game Dev Crew agents, teams, and workflows."""

from __future__ import annotations

from pathlib import Path

from agno.db.base import BaseDb
from agno.os import AgentOS
from agno.registry import Registry

from game_dev_crew.component_persistence import persist_code_defined_components
from game_dev_crew.config import load_env, make_agent_db, make_model, repo_root, tracing_enabled
from game_dev_crew.crew.agents import build_agents
from game_dev_crew.crew.teams import build_game_dev_crew_team, build_specialists_team
from game_dev_crew.knowledge import build_game_dev_knowledge, seed_default_knowledge
from game_dev_crew.os_routes import (
    attach_registry_query_normalize,
    attach_system_components_routes,
    patch_agentos_components_list,
    patch_agentos_workflows_list,
)
from game_dev_crew.tools.policy import crew_tools
from game_dev_crew.workflow.audit_flow import build_audit_workflow
from game_dev_crew.workflow.registry_functions import collect_workflow_functions_for_registry
from game_dev_crew.workflow.scene_generation_flow import build_scene_generation_workflow

_AGENT_OS_CONFIG = Path(__file__).resolve().parent / "agent_os_config.yaml"


def build_app():
    """Construct AgentOS and return the FastAPI application."""
    load_env()
    root = repo_root()
    db = make_agent_db()
    kb = build_game_dev_knowledge(db)
    if kb is not None:
        seed_default_knowledge(kb)
    agents = list(build_agents(root, game_knowledge=kb).values())
    teams = [
        build_specialists_team(root, game_knowledge=kb),
        build_game_dev_crew_team(root, game_knowledge=kb),
    ]
    workflows = [
        build_audit_workflow(repo_root_arg=root, game_knowledge=kb, db=db),
        build_scene_generation_workflow(repo_root_arg=root, game_knowledge=kb, db=db),
    ]
    persist_code_defined_components(
        root,
        db=db,
        agents=agents,
        teams=teams,
        workflows=workflows,
    )
    registry = Registry()
    registry.functions.extend(collect_workflow_functions_for_registry(workflows))
    # Studio GET /registry only serializes registry.* lists (not Agent-inlined tools/models).
    registry.models.append(make_model())
    registry.tools.extend(crew_tools(root))
    if db is not None:
        registry.dbs.append(db)
    if kb is not None:
        vdb = getattr(kb, "vector_db", None)
        if vdb is not None:
            registry.vector_dbs.append(vdb)
    agent_os = AgentOS(
        id="agno-game-dev-crew",
        name="Agno Game Dev Crew",
        description="Agents, teams, AuditFlow, and Scene generation for game/engine work (REPO_ROOT)",
        db=db,
        agents=agents,
        teams=teams,
        workflows=workflows,
        knowledge=[kb] if kb is not None else None,
        config=str(_AGENT_OS_CONFIG),
        tracing=tracing_enabled(),
        registry=registry,
    )
    app = agent_os.get_app()
    patch_agentos_workflows_list(app, agent_os)
    if db is not None and isinstance(db, BaseDb):
        patch_agentos_components_list(app, db)
    attach_registry_query_normalize(app)
    attach_system_components_routes(app)
    return app


app = build_app()
