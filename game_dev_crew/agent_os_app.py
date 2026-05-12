"""AgentOS FastAPI app: exposes Game Dev Crew agents, teams, and AuditFlow."""

from __future__ import annotations

from pathlib import Path

from agno.db.base import BaseDb
from agno.os import AgentOS

from game_dev_crew.component_persistence import persist_code_defined_components
from game_dev_crew.config import load_env, make_agent_db, repo_root, tracing_enabled
from game_dev_crew.crew.agents import build_agents
from game_dev_crew.crew.teams import build_game_dev_crew_team, build_specialists_team
from game_dev_crew.knowledge import build_game_dev_knowledge, seed_default_knowledge
from game_dev_crew.os_routes import attach_system_components_routes, patch_agentos_components_list
from game_dev_crew.workflow.audit_flow import build_audit_workflow

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
    workflows = [build_audit_workflow(repo_root_arg=root, game_knowledge=kb)]
    persist_code_defined_components(
        root,
        db=db,
        agents=agents,
        teams=teams,
        workflow=workflows[0],
    )
    agent_os = AgentOS(
        id="agno-game-dev-crew",
        name="Agno Game Dev Crew",
        description="Agents, teams, and AuditFlow for game/engine work (REPO_ROOT)",
        db=db,
        agents=agents,
        teams=teams,
        workflows=workflows,
        knowledge=[kb] if kb is not None else None,
        config=str(_AGENT_OS_CONFIG),
        tracing=tracing_enabled(),
    )
    app = agent_os.get_app()
    if db is not None and isinstance(db, BaseDb):
        patch_agentos_components_list(app, db)
    attach_system_components_routes(app)
    return app


app = build_app()
