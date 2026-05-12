# Add a new Game Dev Crew agent (code + SQLite)

Use this when the user wants a **new Agno agent** in this repo: you implement it in Python and instructions, then persistence writes rows to SQLite via `agent.save()` (same path as AgentOS startup).

## Gather inputs

- **id** (snake_case, stable): used as `Agent(id=…)` and often the instruction file stem.
- **name** (human-readable), **role**, **description** (short strings for Agno UI / Studio).
- **Team membership**: specialists only, full crew, both, or neither (standalone agent still registered in `build_agents` for API use).
- **Knowledge**: mirror **Auditor** (`knowledge`, `search_knowledge`, …) only if this agent needs the LanceDB game KB.
- **Tools**: default is `crew_tools(repo_root)` from [`game_dev_crew/tools/policy.py`](game_dev_crew/tools/policy.py). Do not broaden shell/write access without an explicit user ask.

## Implementation checklist

1. **Instructions** — Add [`game_dev_crew/instructions/<stem>.md`](game_dev_crew/instructions/) (or reuse a stem). This file is the **only** source for `Agent(instructions=…)`: use `load_instruction("<stem>")` like existing agents in [`game_dev_crew/crew/agents.py`](game_dev_crew/crew/agents.py).
2. **Agent** — In `agents.py`, construct `Agent(...)` with the same patterns as peers: `make_model()`, `crew_tools(root)`, `markdown=True`, `metadata=dict(AGENTS_PY_METADATA)`, and `mem_kw` / optional `auditor_kw`-style knowledge block. Append the instance to the dict returned by `build_agents`.
3. **Teams** — Update [`game_dev_crew/crew/teams.py`](game_dev_crew/crew/teams.py) `members=[…]` for `build_specialists_team` and/or `build_game_dev_crew_team` if the user asked for routing or full crew.
4. **AuditFlow / reviewer rework (conditional)** — Only if this agent must be sent back to by the reviewer’s `- ❌ [owner]` lines:
   - Extend `VALID_OWNERS` and `OWNER_ORDER` in [`game_dev_crew/workflow/reviewer_parse.py`](game_dev_crew/workflow/reviewer_parse.py).
   - Align [`game_dev_crew/instructions/reviewer.md`](game_dev_crew/instructions/reviewer.md) checklist owner tags with the parser.
   - Update steps / wiring in [`game_dev_crew/workflow/audit_flow.py`](game_dev_crew/workflow/audit_flow.py) so the workflow can invoke the new role when needed.
5. **Optional**: if the agent id must appear in exports or docs, touch [`README.md`](README.md) or crew overview text — keep changes minimal.

## Persist to SQLite and verify

From the project root (venv active):

```bash
game-dev-crew sync-components
game-dev-crew sqlite-status
```

- `sync-components` seeds knowledge when configured, builds agents/teams/workflow with the same instances AgentOS uses, and calls `persist_code_defined_components` (see [`game_dev_crew/component_persistence.py`](game_dev_crew/component_persistence.py)).
- If SQLite is disabled (`AGNO_MEMORY_DB=none` in the shell, which `load_dotenv` does not override), tell the user to `unset AGNO_MEMORY_DB` or set `AGNO_MEMORY_DB=sqlite`, then rerun.

After `game-dev-crew serve`, `GET /config` should list the new agent id alongside the rest of the crew.

## Tests

If you change `reviewer_parse` or env-driven config, extend or add tests under [`tests/`](tests/) and run `pytest`.
