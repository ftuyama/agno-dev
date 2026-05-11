"""Agno Team definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agno.team import Team
from agno.team.mode import TeamMode

from game_dev_crew.config import load_instruction, make_agent_db, make_model
from game_dev_crew.crew.agents import build_agents


def build_specialists_team(repo_root: Path) -> Team:
    """Route-only team for storytelling + UI/UX + game design."""
    agents = build_agents(repo_root)
    model = make_model()
    db = make_agent_db()
    mem_kw: dict[str, Any] = {}
    if db is not None:
        mem_kw = {"db": db, "update_memory_on_run": True}
    return Team(
        id="game-dev-specialists",
        name="Game Dev Specialists",
        description="Route-only team: storytelling, UI/UX, and game design specialists.",
        model=model,
        mode=TeamMode.route,
        members=[
            agents["storytelling"],
            agents["ui_ux"],
            agents["game_design"],
        ],
        instructions=[load_instruction("team_leader")],
        **mem_kw,
    )


def build_game_dev_crew_team(repo_root: Path) -> Team:
    """Full crew as a coordinated team (leader delegates)."""
    agents = build_agents(repo_root)
    model = make_model()
    db = make_agent_db()
    mem_kw: dict[str, Any] = {}
    if db is not None:
        mem_kw = {"db": db, "update_memory_on_run": True}
    return Team(
        id="game-dev-crew",
        name="Game Dev Crew",
        description="Full crew: auditor, specialists, senior developer, and reviewer.",
        model=model,
        mode=TeamMode.coordinate,
        members=[
            agents["auditor"],
            agents["storytelling"],
            agents["ui_ux"],
            agents["game_design"],
            agents["senior_developer"],
            agents["reviewer"],
        ],
        instructions=[load_instruction("team_leader")],
        **mem_kw,
    )
