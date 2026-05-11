"""AgentOS FastAPI app: exposes Game Dev Crew agents, teams, and AuditFlow."""

from __future__ import annotations

from pathlib import Path

from agno.os import AgentOS

from game_dev_crew.config import load_env, make_agent_db, repo_root
from game_dev_crew.crew.agents import build_agents
from game_dev_crew.crew.teams import build_game_dev_crew_team, build_specialists_team
from game_dev_crew.workflow.audit_flow import build_audit_workflow

_AGENT_OS_CONFIG = Path(__file__).resolve().parent / "agent_os_config.yaml"


def build_app():
    """Construct AgentOS and return the FastAPI application."""
    load_env()
    root = repo_root()
    agents = list(build_agents(root).values())
    teams = [
        build_specialists_team(root),
        build_game_dev_crew_team(root),
    ]
    workflows = [build_audit_workflow(repo_root_arg=root)]
    agent_os = AgentOS(
        id="agno-game-dev-crew",
        name="Agno Game Dev Crew",
        description="Agents, teams, and AuditFlow for game/engine work (REPO_ROOT)",
        db=make_agent_db(),
        agents=agents,
        teams=teams,
        workflows=workflows,
        config=str(_AGENT_OS_CONFIG),
    )
    return agent_os.get_app()


app = build_app()
