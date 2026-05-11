# Agno Game Dev Crew

Python project using [Agno](https://docs.agno.com) with **OpenRouter** (default `openrouter/free`) to run a **Game Dev Crew** and an **AuditFlow** workflow (audit → specialists → senior developer → reviewer, with reviewer-driven rework).

## Package layout (`game_dev_crew/`)

| Path | Role |
|------|------|
| `config.py` | Env, `repo_root()`, `load_instruction()`, `make_model()` |
| `cli.py` | `game-dev-crew` commands |
| `crew/` | `agents.py`, `teams.py` |
| `workflow/` | `audit_flow.py`, `reviewer_parse.py` |
| `tools/` | Repo read / `validate:scenes` tools + `policy.py` |
| `instructions/` | Markdown prompts (exportable) |

## Setup

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY (required for non dry-run)
```

Dependencies are listed in `pyproject.toml`. The package uses **`agno[os]`** so [AgentOS](https://docs.agno.com/agent-os/introduction) (FastAPI runtime + control plane hooks) is available alongside the CLI. Agno’s workflow stack also relies on **FastAPI** and **OpenAI** client types.

## Environment

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | Required for model calls (OpenRouter). |
| `OPENROUTER_MODEL` | Default `openrouter/free`. |
| `REPO_ROOT` | Absolute path to the **game** repository root (directory with `package.json`). When unset, defaults to **this project’s root** (set explicitly if the game lives elsewhere). |
| `ENABLE_VALIDATE_SCENES_TOOL` | When `true`, Reviewer gets `run_validate_scenes` (`npm run validate:scenes` at `REPO_ROOT`). |
| `AUDIT_FLOW_MAX_ITERATIONS` | Default rework cap for `audit-flow` (default `4`). |
| `AGNO_MEMORY_DB` | `sqlite` enables session memory, user memory, and **AgentOS approvals** (unset / `none` disables). |
| `AGNO_MEMORY_SQLITE_PATH` | SQLite file path (default: `.agno_memory.sqlite` in project root). |

## Commands

```bash
game-dev-crew audit-flow "Focus on src/campaigns/calvario/scenes/act1/"
game-dev-crew audit-flow --max-iterations 3 --dry-run
game-dev-crew specialists "How can we improve readability of combat UI?" --stream
game-dev-crew crew "Summarize engine boundaries vs UI" --dry-run
```

`audit-flow` and `serve` require `REPO_ROOT` (or the default root) to contain a `package.json` from the game repo.

### AgentOS (HTTP API)

Serve the same agents, specialist/full teams, and **AuditFlow** workflow over FastAPI (OpenAPI at `/docs`, control plane at `/` per Agno defaults):

```bash
game-dev-crew serve
game-dev-crew serve --host 0.0.0.0 --port 8000 --reload
```

Set `OPENROUTER_API_KEY` in `.env` before calling model-backed endpoints.

Or: `python -m game_dev_crew ...` from this directory after `pip install -e .`.

## Tooling policy

See `game_dev_crew/tools/policy.py`: Auditor gets read-only `read_repo_file`; Reviewer optionally runs allowlisted `npm run validate:scenes`.

## OpenRouter free tier

Free models may be rate-limited; `openrouter/free` picks among available free models. See [OpenRouter free router](https://openrouter.ai/docs/guides/routing/routers/free-router).
