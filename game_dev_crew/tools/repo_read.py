"""Read-only access to files under the game repo root."""

from __future__ import annotations

from pathlib import Path

_MAX_BYTES = 512_000


def _resolved_under_root(root: Path, relative_path: str) -> Path:
    rel = (relative_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        raise ValueError("Empty path; pass a path relative to the repo root")
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise ValueError("Path escapes repo root") from e
    return candidate


def make_read_repo_file_tool(repo_root: Path):
    root = repo_root.resolve()

    def read_repo_file(relative_path: str) -> str:
        """Read a UTF-8 text file from the game repo (read-only).

        Args:
            relative_path: Path relative to repo root, e.g. ``src/engine/core/state.ts``.

        Returns:
            File contents, or an error message string if the file is missing, not UTF-8 text, or too large.
        """
        try:
            path = _resolved_under_root(root, relative_path)
        except ValueError as e:
            return f"read_repo_file error: {e}"

        if not path.is_file():
            return f"read_repo_file: not a file: {path}"

        try:
            size = path.stat().st_size
        except OSError as e:
            return f"read_repo_file: stat failed: {e}"

        if size > _MAX_BYTES:
            return f"read_repo_file: file too large ({size} bytes; max {_MAX_BYTES})"

        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            return f"read_repo_file: read failed: {e}"

    read_repo_file.__name__ = "read_repo_file"
    return read_repo_file
