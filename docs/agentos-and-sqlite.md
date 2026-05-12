# AgentOS, SQLite, and Agno Studio

Long-form notes for this repo. For a short overview, see the [README](../README.md).

## Definitions vs sessions

- **Definitions** (agents, teams, workflows from code) live in `agno_components` and `agno_component_configs`. They are written when you run `game-dev-crew serve` or `game-dev-crew sync-components` (same persistence path as AgentOS startup).
- **Sessions** (`agno_sessions`) and **memories** (`agno_memories`) grow only after you run agents or chats.

Use **`game-dev-crew sqlite-status`** for the resolved SQLite path and row counts. If the path is not under your project directory (common with non-editable installs), set **`AGNO_MEMORY_SQLITE_PATH`** to an absolute path.

## Environment and dotenv

If **`AGNO_MEMORY_DB`** is already set in your shell (for example to `none`), **`python-dotenv` does not override it**. Use `unset AGNO_MEMORY_DB` or align the shell with `.env` before expecting SQLite persistence.

Do not wrap secrets in extra quotes in `.env` (use `KEY=value`, not `KEY='value'`), or the quotes become part of the value.

## Agno Studio vs local AgentOS

- **[os.agno.com/studio/agents](https://os.agno.com/studio/agents)** lists **cloud / account** agents created in Studio (for example “Test”). It does **not** read your local `game-dev-crew serve` instance and will **not** list code-defined crew members such as `auditor` or `storytelling`.
- After **Add OS → Local** with your server URL (for example `http://127.0.0.1:8000`), Studio’s agent picker for that OS comes from **`GET /config`** on your machine — the same agent ids as:

  ```bash
  curl -s http://127.0.0.1:8000/config
  ```

Your code-defined crew rows still exist in **`agno_components`** even when Studio’s cloud list looks unrelated. Do not infer “which agents exist” from **`agno_sessions`** alone.

## `GET /components` vs `GET /config` vs `GET /system/db-components`

AgentOS **`GET /components`** filters out `component_id` values that belong to the in-memory **registry** (code-defined agents and teams). Those rows remain in `agno_components`; they are exposed via **`GET /config`** (`agents`, `teams`, `workflows`). Workflows in SQLite are not in the registry id set in the same way, so **`GET /components?component_type=workflow`** may still return workflows such as `audit-flow`.

To list **all** SQLite component rows (including registry-backed agents) over HTTP, use **`GET /system/db-components`** (supports the same `component_type`, `page`, and `limit` query parameters as `/components`). This route is registered by this project’s app wiring.

## Where to look in OpenAPI

- **`/docs`** — Interactive OpenAPI for your local AgentOS.
- **`GET /config`** — Agents, teams, and workflows served by this OS.

Replace `http://127.0.0.1:8000` with your bind host and port when following links from local docs.
