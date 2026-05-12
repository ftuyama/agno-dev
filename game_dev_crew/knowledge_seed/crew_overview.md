# Game Dev Crew (Agno)

This knowledge base backs **AgentOS Studio → Knowledge** and optional **Auditor** RAG search.

## What this crew does

- **Auditor**: static analysis and risk review against `REPO_ROOT` (the game repo).
- **Specialists**: storytelling, UI/UX, game design.
- **Senior developer**: TypeScript plans and textual patches.
- **Reviewer**: quality gate and optional `validate:scenes` when enabled.
- **AuditFlow**: audit → specialists → senior → reviewer with reviewer-driven rework.

## Conventions

- `REPO_ROOT` in `.env` points at the game monorepo (directory with `package.json`). If unset, the Agno project root is used.
- Session and knowledge **contents** metadata live in the same SQLite DB as agents when `AGNO_MEMORY_DB` is sqlite (default).
- Vector embeddings for this base are stored under `.agno_lancedb/` (LanceDB on disk).

## Quick prompts

Use AgentOS chat quick prompts for each agent id (`auditor`, `storytelling`, `audit-flow`, etc.); see `agent_os_config.yaml`.
