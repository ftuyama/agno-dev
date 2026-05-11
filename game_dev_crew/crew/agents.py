"""Construct Agno agents for the Game Dev Crew."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agno.agent import Agent

from game_dev_crew.config import load_instruction, make_agent_db, make_model
from game_dev_crew.tools.policy import auditor_tools, reviewer_tools, senior_developer_tools


def _inst(name: str) -> list[str]:
    return [load_instruction(name)]


def build_agents(repo_root: Path) -> dict[str, Agent]:
    root = repo_root.resolve()
    model = make_model()
    db = make_agent_db()
    mem_kw: dict[str, Any] = {}
    if db is not None:
        mem_kw = {"db": db, "update_memory_on_run": True}

    auditor = Agent(
        id="auditor",
        name="Auditor",
        role="Static analysis and codebase risk review for the game repo (REPO_ROOT)",
        model=model,
        instructions=_inst("auditor"),
        tools=auditor_tools(root),
        markdown=True,
        **mem_kw,
    )

    storytelling = Agent(
        id="storytelling",
        name="Storytelling specialist",
        role="Narrative, pacing, branching, PT-BR player-facing prose for calvario",
        model=model,
        instructions=_inst("storytelling"),
        markdown=True,
        **mem_kw,
    )

    ui_ux = Agent(
        id="ui_ux",
        name="UI/UX game specialist",
        role="Readability, UI hierarchy, CSS tokens and accessibility for the IF UI",
        model=model,
        instructions=_inst("ui_ux"),
        markdown=True,
        **mem_kw,
    )

    game_design = Agent(
        id="game_design",
        name="Game designer specialist",
        role="Mechanics aligned with engine schema, combat, progression",
        model=model,
        instructions=_inst("game_design"),
        markdown=True,
        **mem_kw,
    )

    senior_developer = Agent(
        id="senior_developer",
        name="Senior developer",
        role="TypeScript implementation plans and textual patches",
        model=model,
        instructions=_inst("senior_developer"),
        tools=senior_developer_tools(root),
        markdown=True,
        **mem_kw,
    )

    reviewer = Agent(
        id="reviewer",
        name="Reviewer",
        role="Quality gate with parseable checklist and optional validate:scenes tool",
        model=model,
        instructions=_inst("reviewer"),
        tools=reviewer_tools(root),
        markdown=True,
        **mem_kw,
    )

    return {
        "auditor": auditor,
        "storytelling": storytelling,
        "ui_ux": ui_ux,
        "game_design": game_design,
        "senior_developer": senior_developer,
        "reviewer": reviewer,
    }
