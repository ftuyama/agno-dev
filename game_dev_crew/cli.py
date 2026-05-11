"""CLI entry for Game Dev Crew."""

from __future__ import annotations

import argparse
import os
import sys

from game_dev_crew.config import audit_flow_max_iterations, load_env, repo_root
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

    return p


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
