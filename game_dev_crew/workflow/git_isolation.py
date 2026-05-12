"""Git isolation helpers for AuditFlow runs.

The AuditFlow write loop never edits ``main`` directly. Each run creates a
throwaway branch (``agno/audit-flow/<UTC-timestamp>``) off the current HEAD
and commits one change-set per agent per iteration, so the reviewer can
verify the patched tree and the human can inspect / merge / discard the
branch afterwards.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


class GitIsolationError(RuntimeError):
    """Raised when a git precondition for the audit loop is not met."""


def _git() -> str:
    git = shutil.which("git")
    if not git:
        raise GitIsolationError("git not found on PATH")
    return git


def _run_git(repo_root: Path, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_git(), *args],
        cwd=os.fspath(repo_root.resolve()),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        input=input_text,
    )


def _ensure_git_repo(repo_root: Path) -> None:
    if not (repo_root.resolve() / ".git").exists():
        raise GitIsolationError(f"not a git repository: {repo_root}")


def ensure_clean_tree(repo_root: Path) -> None:
    """Raise :class:`GitIsolationError` if the working tree has uncommitted changes.

    Untracked files count: they would be silently committed by ``git add -A``
    later in the loop, which the user almost never wants.
    """
    _ensure_git_repo(repo_root)
    proc = _run_git(repo_root, "status", "--porcelain")
    if proc.returncode != 0:
        raise GitIsolationError(
            f"git status failed (exit_code={proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    if proc.stdout.strip():
        raise GitIsolationError(
            "working tree is not clean. AuditFlow needs a clean tree so the "
            "audit branch only contains agent-authored changes.\n"
            "Stash, commit, or discard your changes, then retry. Offending entries:\n"
            + proc.stdout.rstrip()
        )


def current_branch(repo_root: Path) -> str:
    """Return the currently checked-out branch name, or empty for detached HEAD."""
    _ensure_git_repo(repo_root)
    proc = _run_git(repo_root, "branch", "--show-current")
    if proc.returncode != 0:
        raise GitIsolationError(
            f"git branch --show-current failed: {(proc.stderr or proc.stdout).strip()}"
        )
    return proc.stdout.strip()


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_audit_branch(repo_root: Path, prefix: str = "agno/audit-flow") -> str:
    """Create and switch to a fresh ``<prefix>/<UTC-timestamp>`` branch.

    Returns the branch name. Raises :class:`GitIsolationError` if the branch
    cannot be created (e.g. name collision in the same second).
    """
    _ensure_git_repo(repo_root)
    branch = f"{prefix}/{_utc_timestamp()}"
    proc = _run_git(repo_root, "checkout", "-b", branch)
    if proc.returncode != 0:
        raise GitIsolationError(
            f"git checkout -b {branch} failed (exit_code={proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    return branch


def _has_staged_or_unstaged_changes(repo_root: Path) -> bool:
    proc = _run_git(repo_root, "status", "--porcelain")
    return bool(proc.stdout.strip())


def commit_after(
    repo_root: Path,
    iteration_index: int,
    agent_id: str,
    *,
    run_label: str = "audit-flow",
) -> str | None:
    """Stage everything and commit changes attributed to ``agent_id``.

    Returns the new commit SHA, or ``None`` if there was nothing to commit.
    Used by workflow executors after each agent run so the per-author
    history on the working branch reflects who touched which files.

    ``run_label`` appears in the commit subject (default ``audit-flow`` for AuditFlow).
    """
    _ensure_git_repo(repo_root)

    if not _has_staged_or_unstaged_changes(repo_root):
        return None

    add = _run_git(repo_root, "add", "-A")
    if add.returncode != 0:
        raise GitIsolationError(
            f"git add -A failed: {(add.stderr or add.stdout).strip()}"
        )

    if not _has_staged_or_unstaged_changes(repo_root):
        return None

    message = f"[{run_label} iter {iteration_index}] {agent_id}"
    commit = _run_git(
        repo_root,
        "-c", "commit.gpgsign=false",
        "commit",
        "--no-verify",
        "-m", message,
    )
    if commit.returncode != 0:
        err = (commit.stderr or commit.stdout).strip()
        if "nothing to commit" in err.lower():
            return None
        raise GitIsolationError(f"git commit failed: {err}")

    sha = _run_git(repo_root, "rev-parse", "HEAD")
    if sha.returncode != 0:
        raise GitIsolationError(
            f"git rev-parse HEAD failed: {(sha.stderr or sha.stdout).strip()}"
        )
    return sha.stdout.strip()


def changed_files_in_last_commit(repo_root: Path) -> list[str]:
    """Return the list of paths touched by ``HEAD`` (relative to repo root)."""
    _ensure_git_repo(repo_root)
    proc = _run_git(repo_root, "diff", "--name-only", "HEAD~1", "HEAD")
    if proc.returncode != 0:
        # First commit on a branch may have no parent; fall back to listing all
        # files in the commit.
        proc = _run_git(repo_root, "show", "--name-only", "--pretty=format:", "HEAD")
        if proc.returncode != 0:
            return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def summarize_diff(repo_root: Path, branch: str, base: str = "main") -> str:
    """Return ``git diff <base>...<branch> --stat`` output (best effort).

    Used by the CLI to surface the net effect of the audit run at the end.
    Falls back gracefully if ``base`` does not resolve (e.g. the user works
    on a fork without ``main``).
    """
    _ensure_git_repo(repo_root)
    proc = _run_git(repo_root, "--no-pager", "diff", f"{base}...{branch}", "--stat")
    if proc.returncode != 0:
        return (
            f"(could not compute diff {base}...{branch}: "
            f"{(proc.stderr or proc.stdout).strip()})"
        )
    return proc.stdout.rstrip()
