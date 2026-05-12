---
name: game-dev-crew
description: >-
  This repository (agno-game-dev-crew) — OpenRouter, AuditFlow, AgentOS, SQLite
  persistence, CLI, and how to add agents. Use when editing game_dev_crew,
  running game-dev-crew, sync-components, REPO_ROOT, or Cursor command new-game-dev-agent.
---

# Game Dev Crew (this repo)

## What this is

Python package **`game_dev_crew`**: Agno agents, teams, **AuditFlow** workflow, optional **AgentOS** (`serve`). Models default to OpenRouter (`openrouter/free` unless overridden).

## Layout

| Area | Path |
|------|------|
| CLI entry | `game_dev_crew/cli.py` → script `game-dev-crew` |
| Command metadata | `game_dev_crew/cli_commands.py` |
| Env, model, DB | `game_dev_crew/config.py` |
| Persist definitions | `game_dev_crew/component_persistence.py`; CLI **`sync-components`** |
| AgentOS app | `game_dev_crew/agent_os_app.py` |
| Agents / teams | `crew/agents.py`, `crew/teams.py` |
| Workflow | `workflow/audit_flow.py`, `workflow/reviewer_parse.py` |

## Commands

Run **`game-dev-crew commands`** for a stable list with examples, or **`game-dev-crew --help`**.

- **`sync-components`** — After changing Python or instructions, persist agents, teams, and workflows (AuditFlow + Scene generation) to SQLite (`agent.save()` / `team.save()` / `workflow.save()`). Requires SQLite enabled (`AGNO_MEMORY_DB` not `none` in the shell; `python-dotenv` does not override an already-exported shell variable).
- **`sqlite-status`** — Resolved DB path and `agno_*` table row counts.
- **`serve`** — AgentOS FastAPI app; persists on startup like `sync-components` when DB is on.

## Game repository

Set **`REPO_ROOT`** to the directory that contains the game’s **`package.json`** when the game is not co-located with this package. `audit-flow` and `serve` expect that file at `REPO_ROOT`.

- **Example game:** [*A Masmorra do Silêncio*](https://ftuyama.github.io/silent-dungeon/) (`silent-dungeon`) — point **`REPO_ROOT`** at that clone; KB seeds in `game_dev_crew/knowledge_seed/` (`silent_dungeon_premise.md`, `silent_dungeon_scene_workflow.md`) are onboarding summaries—schemas and scenes remain authoritative only under **`REPO_ROOT`** (e.g. `src/engine/schema/`, `src/campaigns/calvario/`).

## Adding an agent

Use the Cursor command checklist: [`.cursor/commands/new-game-dev-agent.md`](.cursor/commands/new-game-dev-agent.md) (instructions + `agents.py` + teams; conditional AuditFlow / `reviewer_parse`).

Generic Agno framework patterns: [`.cursor/skills/agno/SKILL.md`](.cursor/skills/agno/SKILL.md).

## Deep dives

SQLite, Studio vs local OS, `/components` vs `/system/db-components`: [`docs/agentos-and-sqlite.md`](docs/agentos-and-sqlite.md).

## Tests

```bash
pip install -e ".[dev]"
pytest
```
