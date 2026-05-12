# Agno Game Dev Crew

Python project using [Agno](https://docs.agno.com) with **OpenRouter** (default `openrouter/free`) to run a **Game Dev Crew** and an **AuditFlow** workflow (audit → specialists → senior developer → reviewer, with reviewer-driven rework).

## Package layout (`game_dev_crew/`)

| Path | Role |
|------|------|
| `config.py` | Env, `repo_root()`, `load_instruction()`, `make_model()`, `make_agent_db()` |
| `component_persistence.py` | On AgentOS startup: `agent.save()` / `team.save()` / `workflow.save()` into SQLite |
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
| `AGNO_MEMORY_DB` | Default **sqlite** (when unset): sessions, memories, workflow runs, **AgentOS**, and—on **`serve`**—serialized **agent / team / workflow definitions** (`agent.save()` / `team.save()` / `workflow.save()` into the component store). Set to `none` (or `off` / `false` / `0`) to disable. If the variable is **already set in the shell**, `python-dotenv` does not override it—`unset AGNO_MEMORY_DB` or align the shell with `.env`. |
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
game-dev-crew sqlite-status   # show resolved SQLite path + row counts (definitions vs sessions)
game-dev-crew sync-components   # persist agents/teams/workflow to SQLite without starting the server
game-dev-crew serve
game-dev-crew serve --host 0.0.0.0 --port 8000 --reload
```

Set `OPENROUTER_API_KEY` in `.env` before calling model-backed endpoints. Do not wrap the key in extra quotes in `.env` (use `KEY=value`, not `KEY='value'`), or the quotes become part of the value.

Or: `python -m game_dev_crew ...` from this directory after `pip install -e .`.

### Debugging SQLite persistence

- **Definitions** (agents, teams, workflows from code) live in `agno_components` / `agno_component_configs` — filled when you run `game-dev-crew serve` or `sync-components`.
- **Sessions** (`agno_sessions`) and **memories** (`agno_memories`) grow only after you actually run agents / chats.
- Run **`game-dev-crew sqlite-status`** to print the resolved file path and table row counts. If the path is not under your repo, set **`AGNO_MEMORY_SQLITE_PATH`** to an absolute path (common when the package is installed without `-e`).
- **Agno Studio** may only list agents you created inside Studio (e.g. `test`). Your code-defined crew still lives in **`agno_components`** — use `sqlite-status`, `sync-components` post-output, or run SQL on that table. Do not use **`agno_sessions`** alone to infer which agents exist.
- **Studio URL** [os.agno.com/studio/agents](https://os.agno.com/studio/agents) shows **account** agents, not your local AgentOS. After **Add OS → Local →** your `serve` URL (e.g. `http://127.0.0.1:8000`), open that **OS** in Studio to run the crew; verify with `curl -s http://127.0.0.1:8000/config` and inspect the `agents` array.

### AgentOS `GET /components` vs SQLite

AgentOS [`GET /components`](http://127.0.0.1:8000/docs#/Components/list_components) **filters out** every `component_id` that belongs to the in-memory **registry** (your code-defined agents and teams). Those rows still exist in `agno_components`; they are exposed via [`GET /config`](http://127.0.0.1:8000/docs#/Core/get_config) (`agents`, `teams`, `workflows`). Workflows in SQLite are **not** in the registry ID set, so `GET /components?component_type=workflow` can still return `audit-flow`.

To list **all** SQLite component rows (including crew agents) over HTTP, use **`GET /system/db-components`** (same `component_type`, `page`, `limit` query params as `/components`). This route is always registered.

### Agno Studio: two different “agent” lists

| Where | What you see |
|-------|----------------|
| [os.agno.com/studio/agents](https://os.agno.com/studio/agents) | **Cloud / Studio-created** agents tied to your Agno account (e.g. **Test**). This list does **not** read your `game-dev-crew serve` `/config` and will **not** show `auditor`, `storytelling`, etc. |
| **Local OS** in Studio (after **Add OS → Local** → `http://127.0.0.1:8000`) | The same agents as `curl …/config`: your six crew agents. Use **chat or run** from that connected OS; the agent picker there comes from your server, not from `/studio/agents`. |

## Tooling policy

See `game_dev_crew/tools/policy.py`: Auditor gets read-only `read_repo_file`; Reviewer optionally runs allowlisted `npm run validate:scenes`.

## OpenRouter free tier

Free models may be rate-limited; `openrouter/free` picks among available free models. See [OpenRouter free router](https://openrouter.ai/docs/guides/routing/routers/free-router).
