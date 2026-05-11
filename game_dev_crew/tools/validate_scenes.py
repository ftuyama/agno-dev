"""Run allowlisted scene validation at repo root (npm)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def make_run_validate_scenes_tool(repo_root: Path):
    root = repo_root.resolve()

    def run_validate_scenes() -> str:
        """Run ``npm run validate:scenes`` at the game repo root (``REPO_ROOT``).

        Returns:
            Combined stdout/stderr and exit summary for the reviewer.
        """
        npm = shutil.which("npm")
        if not npm:
            return "run_validate_scenes: npm not found on PATH"

        if not (root / "package.json").is_file():
            return f"run_validate_scenes: no package.json at {root}"

        try:
            proc = subprocess.run(
                [npm, "run", "validate:scenes"],
                cwd=os.fspath(root),
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "run_validate_scenes: timed out after 600s"
        except OSError as e:
            return f"run_validate_scenes: failed to spawn npm: {e}"

        out = (proc.stdout or "") + ("\n" if proc.stderr else "") + (proc.stderr or "")
        tail = out[-24_000:] if len(out) > 24_000 else out
        return f"exit_code={proc.returncode}\n{tail}"

    run_validate_scenes.__name__ = "run_validate_scenes"
    return run_validate_scenes
