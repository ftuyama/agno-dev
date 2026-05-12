"""CLI entry for Game Dev Crew."""

from __future__ import annotations

import argparse
import os
import sys

from game_dev_crew.config import (
    audit_flow_max_iterations,
    load_env,
    make_agent_db,
    memory_sqlite_file,
    repo_root,
)
from game_dev_crew.crew.teams import build_game_dev_crew_team, build_specialists_team
from game_dev_crew.workflow.audit_flow import build_audit_workflow, format_audit_cli_report, run_audit_flow


def _die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def cmd_audit_flow(args: argparse.Namespace) -> None:
    load_env()
    root = repo_root()
    if not (root / "package.json").is_file():
        _die(
            "REPO_ROOT must point at the game repo (directory with package.json). "
            f"Got: {root}"
        )

    if args.dry_run:
        wf = build_audit_workflow(repo_root_arg=root, max_iterations=args.max_iterations)
        print("Dry run: workflow built OK:", wf.name)
        print("Repo root:", root)
        print("Would run AuditFlow with prompt:\n", args.prompt)
        return

    if not os.environ.get("OPENROUTER_API_KEY"):
        _die("OPENROUTER_API_KEY is not set. Copy .env.example to .env or export the variable.")

    out = run_audit_flow(
        args.prompt,
        repo_root_arg=root,
        max_iterations=args.max_iterations,
    )
    print(format_audit_cli_report(out))


def cmd_specialists(args: argparse.Namespace) -> None:
    load_env()
    if not args.dry_run and not os.environ.get("OPENROUTER_API_KEY"):
        _die("OPENROUTER_API_KEY is not set.")
    team = build_specialists_team(repo_root())
    if args.dry_run:
        print("Dry run: specialists team:", team.name)
        print("Prompt:", args.prompt)
        return
    team.print_response(args.prompt, stream=bool(args.stream))


def cmd_sqlite_status(args: argparse.Namespace) -> None:
    """Print which SQLite file is used and row counts (definitions vs chat sessions)."""
    import sqlite3

    import game_dev_crew.config as cfg

    load_env()
    path = memory_sqlite_file()
    raw_mem = os.environ.get("AGNO_MEMORY_DB", "")
    raw_sqlite_path = os.environ.get("AGNO_MEMORY_SQLITE_PATH", "")

    print("game_dev_crew.config loaded from:", cfg.__file__)
    print("Package data dir (_AGNO_DIR):", cfg._AGNO_DIR)
    print("AGNO_MEMORY_DB (effective env):", repr(raw_mem.strip() or "(empty → default sqlite)"))
    print("AGNO_MEMORY_SQLITE_PATH (env):", repr(raw_sqlite_path.strip() or "(unset → project .agno_memory.sqlite)"))
    print("Resolved main SQLite file:", path)
    db_inst = make_agent_db()
    print("make_agent_db():", type(db_inst).__name__ if db_inst else None)

    if not path.is_file():
        print("\nFile does not exist yet. Run: game-dev-crew sync-components")
        print("If you use a non-editable install, paths are relative to site-packages — set AGNO_MEMORY_SQLITE_PATH to an absolute path.")
        return

    con = sqlite3.connect(path)
    try:
        tables = [
            ("agno_components", "saved agent/team/workflow definitions (agent.save / team.save / workflow.save)"),
            ("agno_component_configs", "versioned JSON configs for those components"),
            ("agno_sessions", "chat / run sessions (fills after you talk to an agent)"),
            ("agno_memories", "user memories when enabled"),
        ]
        print("\nRow counts:")
        for table, hint in tables:
            try:
                n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                n = "(no such table)"
            print(f"  {table}: {n}")
            print(f"      → {hint}")
        rows = con.execute(
            "SELECT component_id, component_type FROM agno_components ORDER BY component_type, component_id"
        ).fetchall()
        if rows:
            print("\nagno_components rows:")
            for cid, ctype in rows:
                print(f"    {ctype:12}  {cid}")
        print(
            "\nNote: Agno Studio may only list agents you created in the Studio UI. "
            "Code-defined crew agents are in the agno_components table (above)."
        )
    finally:
        con.close()


def cmd_sync_components(args: argparse.Namespace) -> None:
    """Persist agents, teams, and AuditFlow into SQLite (same logic as AgentOS startup)."""
    from game_dev_crew.component_persistence import persist_code_defined_components
    from game_dev_crew.crew.agents import build_agents
    from game_dev_crew.crew.teams import build_game_dev_crew_team, build_specialists_team
    from game_dev_crew.knowledge import build_game_dev_knowledge, seed_default_knowledge
    from game_dev_crew.workflow.audit_flow import build_audit_workflow

    load_env()
    root = repo_root()
    db = make_agent_db()
    if db is None:
        _die(
            "SQLite do AgentOS está desligado (make_agent_db() == None).\n"
            "- No .env: AGNO_MEMORY_DB=sqlite ou omita (default sqlite).\n"
            "- Se a shell exporta AGNO_MEMORY_DB=none, faça: unset AGNO_MEMORY_DB\n"
            "  (python-dotenv não sobrepõe variáveis já definidas na shell).\n"
            f"- Caminho do ficheiro quando ativo: {memory_sqlite_file()}"
        )
    kb = build_game_dev_knowledge(db)
    if kb is not None:
        seed_default_knowledge(kb)
    agents = list(build_agents(root, game_knowledge=kb).values())
    teams = [
        build_specialists_team(root, game_knowledge=kb),
        build_game_dev_crew_team(root, game_knowledge=kb),
    ]
    workflows = [build_audit_workflow(repo_root_arg=root, game_knowledge=kb)]
    if not persist_code_defined_components(
        root,
        db=db,
        agents=agents,
        teams=teams,
        workflow=workflows[0],
    ):
        _die("persist_code_defined_components falhou (BaseDb ausente).")
    path = memory_sqlite_file()
    print("Componentes gravados em:", path)
    import sqlite3

    con = sqlite3.connect(str(path))
    try:
        agents_db = con.execute(
            "SELECT component_id FROM agno_components "
            "WHERE component_type = 'agent' AND deleted_at IS NULL ORDER BY component_id"
        ).fetchall()
        teams_db = con.execute(
            "SELECT component_id FROM agno_components "
            "WHERE component_type = 'team' AND deleted_at IS NULL ORDER BY component_id"
        ).fetchall()
        wf_db = con.execute(
            "SELECT component_id FROM agno_components "
            "WHERE component_type = 'workflow' AND deleted_at IS NULL ORDER BY component_id"
        ).fetchall()
    finally:
        con.close()
    print("Verification from table agno_components (do not confuse with agno_sessions):")
    print("  agents:   ", ", ".join(r[0] for r in agents_db) or "(none)")
    print("  teams:    ", ", ".join(r[0] for r in teams_db) or "(none)")
    print("  workflows:", ", ".join(r[0] for r in wf_db) or "(none)")


def cmd_serve(args: argparse.Namespace) -> None:
    """Run AgentOS (FastAPI) — same agents/teams/workflow as the CLI."""
    import uvicorn

    load_env()
    root = repo_root()
    if not (root / "package.json").is_file():
        _die(
            "REPO_ROOT must point at the game repo (directory with package.json). "
            f"Got: {root}"
        )

    if make_agent_db() is None:
        print(
            "game-dev-crew serve: SQLite do AgentOS está desligado — definições de agentes/equipas "
            "não serão gravadas (AGNO_MEMORY_DB=none na shell ou no .env; load_dotenv não sobrepõe a shell).",
            file=sys.stderr,
        )
        print(f"                  Caminho usado quando o SQLite está ativo: {memory_sqlite_file()}", file=sys.stderr)

    connect_host = "127.0.0.1" if args.host in ("0.0.0.0", "::", "[::]") else args.host
    base_url = f"http://{connect_host}:{args.port}"
    print(
        "\n--- Agno Studio (os.agno.com) ---\n"
        f"• Add OS → Local → {base_url} (while this server is running).\n"
        "• The page https://os.agno.com/studio/agents lists **cloud account** agents (e.g. “Test”), "
        "not your Game Dev Crew from this repo.\n"
        "• Use your **connected local OS** in Studio (chat / run) to reach auditor, storytelling, … "
        "from /config on this server.\n"
        "• GET /components lists all rows in agno_components (agents, teams, workflows). "
        "GET /system/db-components is the same data without AgentOS auth (debug).\n"
        f"• Check: curl -s {base_url}/config | python3 -c "
        "\"import json,sys; d=json.load(sys.stdin); print([a.get('id') for a in d.get('agents',[])])\"\n",
        file=sys.stderr,
    )

    uvicorn.run(
        "game_dev_crew.agent_os_app:app",
        host=args.host,
        port=args.port,
        factory=False,
        reload=args.reload,
    )


def cmd_crew(args: argparse.Namespace) -> None:
    load_env()
    if not args.dry_run and not os.environ.get("OPENROUTER_API_KEY"):
        _die("OPENROUTER_API_KEY is not set.")
    team = build_game_dev_crew_team(repo_root())
    if args.dry_run:
        print("Dry run: full crew team:", team.name)
        print("Prompt:", args.prompt)
        return
    team.print_response(args.prompt, stream=bool(args.stream))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Agno Game Dev Crew (OpenRouter, AuditFlow)")
    sub = p.add_subparsers(dest="command", required=True)

    af = sub.add_parser("audit-flow", help="Run AuditFlow (auditor → specialists → senior → reviewer, rework loop)")
    af.add_argument(
        "prompt",
        nargs="?",
        default="Audit the game codebase for risks and improvements; start with src/engine/ and src/campaigns/calvario/scenes/.",
        help="Scope / instructions for the audit",
    )
    af.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help=f"Max rework loop iterations (default env AUDIT_FLOW_MAX_ITERATIONS or {audit_flow_max_iterations()})",
    )
    af.add_argument("--dry-run", action="store_true", help="Validate wiring only; no API calls")
    af.set_defaults(func=cmd_audit_flow)

    sp = sub.add_parser("specialists", help="Route-only team (storytelling, ui_ux, game_design)")
    sp.add_argument("prompt", help="Question for the specialists team")
    sp.add_argument("--stream", action="store_true", help="Stream tokens to stdout")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_specialists)

    cr = sub.add_parser("crew", help="Full coordinated team (all agents)")
    cr.add_argument("prompt", help="Question for the Game Dev Crew")
    cr.add_argument("--stream", action="store_true")
    cr.add_argument("--dry-run", action="store_true")
    cr.set_defaults(func=cmd_crew)

    sv = sub.add_parser("serve", help="Run AgentOS API (FastAPI) for agents, teams, and AuditFlow")
    sv.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    sv.add_argument("--port", type=int, default=8000, help="Port (default 8000)")
    sv.add_argument("--reload", action="store_true", help="Dev auto-reload on code changes")
    sv.set_defaults(func=cmd_serve)

    sy = sub.add_parser(
        "sync-components",
        help="Gravar agentes, equipas e AuditFlow no SQLite (sem levantar o servidor)",
    )
    sy.set_defaults(func=cmd_sync_components)

    st = sub.add_parser(
        "sqlite-status",
        help="Mostrar ficheiro SQLite resolvido e contagens (definições vs sessões)",
    )
    st.set_defaults(func=cmd_sqlite_status)

    return p


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
