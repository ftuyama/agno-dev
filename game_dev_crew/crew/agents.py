"""Construct Agno agents for the Game Dev Crew."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from agno.agent import Agent
from agno.knowledge.protocol import KnowledgeProtocol

from game_dev_crew.config import load_instruction, make_agent_db, make_model
from game_dev_crew.crew.meta import AGENTS_PY_METADATA
from game_dev_crew.tools.policy import crew_tools


def _inst(name: str) -> list[str]:
    return [load_instruction(name)]


def build_agents(repo_root: Path, game_knowledge: Optional[KnowledgeProtocol] = None) -> dict[str, Agent]:
    root = repo_root.resolve()
    model = make_model()
    db = make_agent_db()
    mem_kw: dict[str, Any] = {}
    if db is not None:
        mem_kw = {
            "db": db,
            "update_memory_on_run": True,
            "enable_agentic_memory": True,
        }

    auditor_kw: dict[str, Any] = dict(mem_kw)
    if game_knowledge is not None:
        auditor_kw["knowledge"] = game_knowledge
        auditor_kw["search_knowledge"] = True
        auditor_kw["add_knowledge_to_context"] = False

    auditor = Agent(
        id="auditor",
        name="Auditor",
        description="Static analysis and codebase risk review for the game repo (REPO_ROOT).",
        role="Static analysis and codebase risk review for the game repo (REPO_ROOT)",
        model=model,
        instructions=_inst("auditor"),
        tools=crew_tools(root),
        markdown=True,
        metadata=dict(AGENTS_PY_METADATA),
        **auditor_kw,
    )

    storytelling = Agent(
        id="storytelling",
        name="Storytelling specialist",
        description="Narrative, pacing, branching, PT-BR player-facing prose for calvario.",
        role="Narrative, pacing, branching, PT-BR player-facing prose for calvario",
        model=model,
        instructions=_inst("storytelling"),
        tools=crew_tools(root),
        markdown=True,
        metadata=dict(AGENTS_PY_METADATA),
        **mem_kw,
    )

    ui_ux = Agent(
        id="ui_ux",
        name="UI/UX game specialist",
        description="Readability, UI hierarchy, CSS tokens and accessibility for the IF UI.",
        role="Readability, UI hierarchy, CSS tokens and accessibility for the IF UI",
        model=model,
        instructions=_inst("ui_ux"),
        tools=crew_tools(root),
        markdown=True,
        metadata=dict(AGENTS_PY_METADATA),
        **mem_kw,
    )

    game_design = Agent(
        id="game_design",
        name="Game designer specialist",
        description="Mechanics aligned with engine schema, combat, progression.",
        role="Mechanics aligned with engine schema, combat, progression",
        model=model,
        instructions=_inst("game_design"),
        tools=crew_tools(root),
        markdown=True,
        metadata=dict(AGENTS_PY_METADATA),
        **mem_kw,
    )

    senior_developer = Agent(
        id="senior_developer",
        name="Senior developer",
        description="TypeScript implementation plans and textual patches.",
        role="TypeScript implementation plans and textual patches",
        model=model,
        instructions=_inst("senior_developer"),
        tools=crew_tools(root),
        markdown=True,
        metadata=dict(AGENTS_PY_METADATA),
        **mem_kw,
    )

    reviewer = Agent(
        id="reviewer",
        name="Reviewer",
        description="Quality gate with parseable checklist; uses the same repo and validate tools as the rest of the crew.",
        role="Quality gate with parseable checklist and full crew repo tools",
        model=model,
        instructions=_inst("reviewer"),
        tools=crew_tools(root),
        markdown=True,
        metadata=dict(AGENTS_PY_METADATA),
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
