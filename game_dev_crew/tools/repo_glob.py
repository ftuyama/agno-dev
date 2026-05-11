"""Glob files under the game repo root (read-only)."""

from __future__ import annotations

from pathlib import Path


def make_glob_repo_tool(repo_root: Path):
    root = repo_root.resolve()

    def glob(pattern: str, limit: int = 400) -> str:
        """List **file** paths under the game repo matching a glob (relative to repo root).

        Use POSIX-style patterns, e.g. ``src/**/*.ts``, ``src/campaigns/calvario/scenes/**/*.md``.
        Does not follow symlinks for traversal control; only paths under the repo root are returned.

        Args:
            pattern: Glob relative to repo root (no ``..``, no absolute paths).
            limit: Max number of paths to return (capped at 2000).

        Returns:
            One path per line, or an error string.
        """
        pat = (pattern or "").strip().replace("\\", "/")
        if not pat:
            return "glob: empty pattern"
        if ".." in pat:
            return "glob: pattern must not contain .."
        if pat.startswith("/"):
            return "glob: pattern must be relative to repo root (no leading /)"

        try:
            lim = max(1, min(int(limit), 2000))
        except (TypeError, ValueError):
            lim = 400

        lines: list[str] = []
        truncated = False
        try:
            for p in root.glob(pat):
                if not p.is_file():
                    continue
                try:
                    rel = p.resolve().relative_to(root)
                except ValueError:
                    continue
                lines.append(rel.as_posix())
                if len(lines) >= lim:
                    truncated = True
                    break
        except OSError as e:
            return f"glob: invalid pattern or IO error: {e}"

        if not lines:
            return "glob: no files matched"
        lines.sort()
        out = "\n".join(lines)
        if truncated:
            out += f"\n(glob: truncated at {lim} files; narrow the pattern)"
        return out

    glob.__name__ = "glob"
    return glob
