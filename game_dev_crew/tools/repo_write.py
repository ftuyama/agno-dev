"""Write access to files under the game repo root.

Every agent in the crew gets ``write_repo_file`` and ``apply_patch`` via
``crew_tools`` in :mod:`game_dev_crew.tools.policy`. Writes are scoped to
anywhere under ``REPO_ROOT`` with a single hard block on ``.git/`` to keep the
audit branch the AuditFlow loop creates from being corrupted.

The AuditFlow executor commits the working tree after each agent runs and
discovers changed files via ``git diff --name-only HEAD~1 HEAD``; these tools
therefore do not maintain their own bookkeeping.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

_MAX_BYTES = 512_000

_BLOCKED_PREFIXES: tuple[str, ...] = (".git/",)
_BLOCKED_FIRST_SEGMENTS: frozenset[str] = frozenset({".git"})

# ``diff --git a/<a> b/<b>`` header.
_DIFF_GIT_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)\s*$", re.MULTILINE)
# Standalone unified-diff path markers (``--- a/<path>`` / ``+++ b/<path>``).
_UNIFIED_PATH_HEADER = re.compile(r"^(?:---|\+\+\+) (?:a/|b/)?(\S+)\s*$", re.MULTILINE)


def _normalize_relative(relative_path: str) -> str:
    return (relative_path or "").strip().replace("\\", "/").lstrip("/")


def _is_blocked_relative(rel: str) -> bool:
    """True for paths inside a blocked top-level directory like ``.git/``."""
    if not rel:
        return False
    first = rel.split("/", 1)[0]
    if first in _BLOCKED_FIRST_SEGMENTS:
        return True
    norm = rel + "/" if not rel.endswith("/") else rel
    return any(norm.startswith(p) for p in _BLOCKED_PREFIXES)


def _resolved_under_root(root: Path, relative_path: str) -> Path:
    rel = _normalize_relative(relative_path)
    if not rel:
        raise ValueError("Empty path; pass a path relative to the repo root")
    if ".." in rel.split("/"):
        raise ValueError("Path must not contain '..'")
    if _is_blocked_relative(rel):
        raise ValueError(f"Path is blocked (cannot write under {_BLOCKED_PREFIXES}): {rel}")
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise ValueError("Path escapes repo root") from e
    return candidate


def _patch_paths(unified_diff: str) -> list[str]:
    """Extract every repo-relative path mentioned in a unified diff.

    Looks at both ``diff --git`` headers and the ``---``/``+++`` markers so
    paths from minimal diffs (no ``diff --git`` line) are also caught.
    """
    paths: list[str] = []
    seen: set[str] = set()

    def _add(p: str) -> None:
        p = p.strip()
        if not p or p in seen:
            return
        if p == "/dev/null":
            return
        norm = p.replace("\\", "/").lstrip("/")
        if norm.startswith("a/") or norm.startswith("b/"):
            norm = norm[2:]
        if not norm or norm in seen:
            return
        seen.add(norm)
        paths.append(norm)

    for m in _DIFF_GIT_HEADER.finditer(unified_diff or ""):
        _add(m.group(1))
        _add(m.group(2))
    for m in _UNIFIED_PATH_HEADER.finditer(unified_diff or ""):
        _add(m.group(1))
    return paths


def make_write_repo_file_tool(repo_root: Path) -> Callable[..., str]:
    """Build a ``write_repo_file`` tool bound to ``repo_root``."""
    root = repo_root.resolve()

    def write_repo_file(relative_path: str, contents: str) -> str:
        """Write ``contents`` to ``relative_path`` under the game repo root.

        Creates missing parent directories. Refuses paths outside the repo
        root, paths containing ``..``, paths under ``.git/``, and content
        larger than 512 KB.

        Args:
            relative_path: Path relative to the repo root,
                e.g. ``src/campaigns/calvario/scenes/intro.md``.
            contents: UTF-8 text to write.

        Returns:
            ``"wrote <path> (<bytes> bytes)"`` on success, or an error
            ``str`` starting with ``"write_repo_file:"`` on refusal.
        """
        try:
            path = _resolved_under_root(root, relative_path)
        except ValueError as e:
            return f"write_repo_file: {e}"

        body = contents if isinstance(contents, str) else str(contents or "")
        encoded = body.encode("utf-8")
        if len(encoded) > _MAX_BYTES:
            return (
                f"write_repo_file: contents too large ({len(encoded)} bytes; "
                f"max {_MAX_BYTES})"
            )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encoded)
        except OSError as e:
            return f"write_repo_file: write failed: {e}"

        rel = path.relative_to(root).as_posix()
        return f"wrote {rel} ({len(encoded)} bytes)"

    write_repo_file.__name__ = "write_repo_file"
    return write_repo_file


def make_apply_patch_tool(repo_root: Path) -> Callable[..., str]:
    """Build an ``apply_patch`` tool bound to ``repo_root``.

    Uses ``git apply --index`` so the resulting changes are also staged,
    which lets the AuditFlow executor commit per-agent without an extra
    ``git add``.
    """
    root = repo_root.resolve()

    def apply_patch(unified_diff: str) -> str:
        """Apply a unified diff at the game repo root via ``git apply``.

        Validates every path mentioned in the patch against the same rules
        as ``write_repo_file`` (no ``..``, no ``.git/``, must resolve under
        the repo root). Rejects the whole patch if any path fails.

        Args:
            unified_diff: A unified diff string. Both ``diff --git`` and
                bare ``--- a/<path>``/``+++ b/<path>`` headers are accepted.

        Returns:
            ``"applied N files: <paths>"`` on success, or an error string
            starting with ``"apply_patch:"`` or ``"git apply error:"``.
        """
        diff = unified_diff if isinstance(unified_diff, str) else str(unified_diff or "")
        if not diff.strip():
            return "apply_patch: empty diff"

        paths = _patch_paths(diff)
        if not paths:
            return "apply_patch: could not find any file paths in diff"

        for p in paths:
            try:
                _resolved_under_root(root, p)
            except ValueError as e:
                return f"apply_patch: rejected path {p!r}: {e}"

        git = shutil.which("git")
        if not git:
            return "apply_patch: git not found on PATH"
        if not (root / ".git").exists():
            return f"apply_patch: not a git repository: {root}"

        try:
            proc = subprocess.run(
                [git, "apply", "--index", "--whitespace=nowarn", "-"],
                cwd=os.fspath(root),
                input=diff,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "apply_patch: timed out after 120s"
        except OSError as e:
            return f"apply_patch: failed to spawn git: {e}"

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            return f"git apply error (exit_code={proc.returncode}):\n{err[-4000:]}"

        return f"applied {len(paths)} files: {', '.join(paths)}"

    apply_patch.__name__ = "apply_patch"
    return apply_patch


__all__ = [
    "make_write_repo_file_tool",
    "make_apply_patch_tool",
]
