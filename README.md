# Agno Game Dev Crew

Python tooling that runs a **Game Dev Crew** and **AuditFlow** on top of [Agno](https://docs.agno.com), using **OpenRouter** (default `openrouter/free`). Flow: audit → specialists → senior developer → reviewer, with reviewer-driven rework.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Set OPENROUTER_API_KEY for real model calls (not required for --dry-run).
```

- **Editable app**: `pip install -e .` — entry point **`game-dev-crew`**.
- **Tests**: `pip install -e ".[dev]"` then **`pytest`**.

## Environment (short)

| Variable | Role |
|----------|------|
| `OPENROUTER_API_KEY` | Required for non–dry-run runs. |
| `OPENROUTER_MODEL` | Default `openrouter/free`. |
| `REPO_ROOT` | Game repo root (directory with `package.json`). Defaults to this package’s parent if unset. |
| `AUDIT_FLOW_MAX_ITERATIONS` | Rework cap for `audit-flow` (default `4`). |
| `AGNO_MEMORY_DB` | Default sqlite; `none` / `off` / `false` / `0` disables DB (shell wins over `.env` if already set). |
| `AGNO_MEMORY_SQLITE_PATH` | SQLite file (default `.agno_memory.sqlite` in project root). |
| `ENABLE_VALIDATE_SCENES_TOOL` | `true` enables `npm run validate:scenes` tooling where policy allows. |

More on SQLite, Studio, and HTTP routes: [docs/agentos-and-sqlite.md](docs/agentos-and-sqlite.md).

## CLI

List everything with copy-paste examples:

```bash
game-dev-crew commands
```

| Command | Purpose |
|---------|---------|
| `audit-flow` | Run AuditFlow on `REPO_ROOT` (`package.json` required). |
| `specialists` | Route-only team (storytelling, ui_ux, game_design). |
| `crew` | Full coordinated team. |
| `serve` | AgentOS (FastAPI); OpenAPI at `/docs`. |
| `sync-components` | Persist agents, teams, workflow to SQLite without HTTP. |
| `sqlite-status` | Show DB path and table row counts. |

`audit-flow` and `serve` expect **`package.json`** under `REPO_ROOT`.

## AgentOS quick start

```bash
game-dev-crew sync-components   # optional: write definitions before first serve
game-dev-crew serve               # http://127.0.0.1:8000 by default
```

## Package layout

| Path | Role |
|------|------|
| `game_dev_crew/config.py` | Env, paths, model, DB factory. |
| `game_dev_crew/cli.py` | CLI. |
| `game_dev_crew/component_persistence.py` | `agent.save()` / `team.save()` / `workflow.save()`. |
| `game_dev_crew/crew/` | `agents.py`, `teams.py`. |
| `game_dev_crew/workflow/` | `audit_flow.py`, `reviewer_parse.py`. |
| `game_dev_crew/tools/` | Read-only and allowlisted shell; see `policy.py`. |
| `game_dev_crew/instructions/` | Markdown prompts for agents. |

## Adding agents

Use the Cursor command [`.cursor/commands/new-game-dev-agent.md`](.cursor/commands/new-game-dev-agent.md): add `instructions/*.md`, wire `crew/agents.py` (and teams / AuditFlow if needed), then run **`game-dev-crew sync-components`**.

## Tooling policy

See [`game_dev_crew/tools/policy.py`](game_dev_crew/tools/policy.py).

## OpenRouter free tier

Free models may be rate-limited. See [OpenRouter free router](https://openrouter.ai/docs/guides/routing/routers/free-router).
