"""Allowlisted ``npm run …`` execution at repo root (no shell, argv only)."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

# Keep in sync with root package.json scripts the crew should be allowed to run.
_ALLOWED_NPM_SCRIPTS: frozenset[str] = frozenset(
    {
        "validate:scenes",
        "validate:unreachable",
        "check:ascii-art",
        "test",
        "check:engine-boundaries",
        "lint:highlight-frames",
    }
)


def _npm_argv_allowed(argv: list[str]) -> bool:
    if len(argv) < 3:
        return False
    if argv[0] != "npm":
        return False
    if argv[1] != "run":
        return False
    return argv[2] in _ALLOWED_NPM_SCRIPTS


def _normalize_to_argv(command: str) -> list[str] | None:
    raw = (command or "").strip()
    if not raw:
        return None
    try:
        return shlex.split(raw, posix=True)
    except ValueError as e:
        raise ValueError(f"could not parse command: {e}") from e


def _run_allowlisted_npm(repo_root: Path, argv: list[str]) -> str:
    root = repo_root.resolve()
    if not _npm_argv_allowed(argv):
        allowed = ", ".join(sorted(_ALLOWED_NPM_SCRIPTS))
        return (
            "execute_command/bash: only allowlisted commands are permitted. "
            f"Use: npm run <script> with script one of: {allowed}. "
            "Example: npm run validate:scenes -- --campaign calvario"
        )

    npm = shutil.which("npm")
    if not npm:
        return "execute_command/bash: npm not found on PATH"

    if not (root / "package.json").is_file():
        return f"execute_command/bash: no package.json at {root}"

    try:
        proc = subprocess.run(
            [npm, *argv[1:]],
            cwd=os.fspath(root),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "execute_command/bash: timed out after 600s"
    except OSError as e:
        return f"execute_command/bash: failed to spawn npm: {e}"

    out = (proc.stdout or "") + ("\n" if proc.stderr else "") + (proc.stderr or "")
    tail = out[-24_000:] if len(out) > 24_000 else out
    return f"exit_code={proc.returncode}\n{tail}"


def make_execute_command_tool(repo_root: Path):
    root = repo_root.resolve()

    def execute_command(command: str) -> str:
        """Run one allowlisted **npm** command at the repo root (no arbitrary shell).

        ``command`` must parse to ``npm run <script>`` with optional extra args after ``--``,
        where ``<script>`` is one of: validate:scenes, validate:unreachable, check:ascii-art,
        test, check:engine-boundaries, lint:highlight-frames.

        Examples:
            ``npm run test``
            ``npm run validate:scenes -- --campaign calvario``

        Returns:
            Combined stdout/stderr with exit_code= prefix.
        """
        try:
            argv = _normalize_to_argv(command)
        except ValueError as e:
            return f"execute_command: {e}"
        if argv is None:
            return "execute_command: empty command"
        return _run_allowlisted_npm(root, argv)

    execute_command.__name__ = "execute_command"
    return execute_command


def make_bash_tool(repo_root: Path):
    root = repo_root.resolve()

    def bash(command: str) -> str:
        """Same allowlist as ``execute_command``: run **npm** at repo root.

        If the string starts with ``bash -c`` / ``sh -c``, the inner command is parsed
        and must again be an allowlisted ``npm run …`` invocation.

        Returns:
            Combined stdout/stderr with exit_code= prefix.
        """
        raw = (command or "").strip()
        if not raw:
            return "bash: empty command"
        try:
            argv = shlex.split(raw, posix=True)
        except ValueError as e:
            return f"bash: could not parse: {e}"

        if len(argv) >= 3 and Path(argv[0]).name in ("bash", "sh") and argv[1] == "-c":
            inner = argv[2]
            try:
                inner_argv = shlex.split(inner.strip(), posix=True)
            except ValueError as e:
                return f"bash: could not parse -c body: {e}"
            return _run_allowlisted_npm(root, inner_argv)

        return _run_allowlisted_npm(root, argv)

    bash.__name__ = "bash"
    return bash
