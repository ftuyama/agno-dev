"""CLI subcommand metadata (single source for help text and `commands` output)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubcommandSpec:
    name: str
    help: str
    example: str


SUBCOMMANDS: tuple[SubcommandSpec, ...] = (
    SubcommandSpec(
        name="audit-flow",
        help="Run AuditFlow (auditor → specialists → senior → reviewer, rework loop)",
        example='game-dev-crew audit-flow "Focus on src/engine/" --dry-run',
    ),
    SubcommandSpec(
        name="scene-generation",
        help="Run Scene generation (storytelling → game design → senior developer; git branch)",
        example='game-dev-crew scene-generation "Add 3 scenes for act 2 escape beat" --dry-run',
    ),
    SubcommandSpec(
        name="specialists",
        help="Route-only team (storytelling, ui_ux, game_design)",
        example='game-dev-crew specialists "How can we improve combat UI?" --stream',
    ),
    SubcommandSpec(
        name="crew",
        help="Full coordinated team (all agents)",
        example='game-dev-crew crew "Summarize engine vs UI boundaries" --dry-run',
    ),
    SubcommandSpec(
        name="serve",
        help="Run AgentOS API (FastAPI) for agents, teams, AuditFlow, and Scene generation",
        example="game-dev-crew serve --host 127.0.0.1 --port 8000 --reload",
    ),
    SubcommandSpec(
        name="sync-components",
        help="Persist agents, teams, and workflows (AuditFlow + Scene generation) to SQLite",
        example="game-dev-crew sync-components",
    ),
    SubcommandSpec(
        name="sqlite-status",
        help="Show resolved SQLite path and row counts (definitions vs sessions)",
        example="game-dev-crew sqlite-status",
    ),
    SubcommandSpec(
        name="commands",
        help="List all subcommands with one-line descriptions and examples",
        example="game-dev-crew commands",
    ),
)


def subcommand_help(name: str) -> str:
    for s in SUBCOMMANDS:
        if s.name == name:
            return s.help
    raise KeyError(name)
