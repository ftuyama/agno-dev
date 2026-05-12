"""Tests for write_repo_file and apply_patch path safety + behaviour."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from game_dev_crew.tools.repo_write import (
    make_apply_patch_tool,
    make_write_repo_file_tool,
)


def _init_git_repo(repo: Path, initial_file: str = "README.md", initial_content: str = "hi\n") -> None:
    repo.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    def _git(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=os.fspath(repo),
            capture_output=True,
            text=True,
            check=True,
            env=env,
            input=input_text,
        )

    _git("init", "--initial-branch=main")
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "Test")
    (repo / initial_file).write_text(initial_content)
    _git("add", initial_file)
    _git("-c", "commit.gpgsign=false", "commit", "-m", "init")


def test_write_repo_file_accepts_any_top_level_path(tmp_path: Path) -> None:
    write = make_write_repo_file_tool(tmp_path)

    for rel in (
        "src/engine/state.ts",
        "docs/audit-notes/security.md",
        "scripts/new-tool.mjs",
        "config/app.json",
        "TOPLEVEL.md",
    ):
        result = write(rel, f"content of {rel}\n")
        assert result.startswith("wrote ")
        assert (tmp_path / rel).read_text() == f"content of {rel}\n"


def test_write_repo_file_rejects_dot_git(tmp_path: Path) -> None:
    write = make_write_repo_file_tool(tmp_path)

    for rel in (".git/config", ".git/refs/heads/main", ".git"):
        result = write(rel, "boom")
        assert result.startswith("write_repo_file:"), result
        assert "blocked" in result.lower() or "path" in result.lower()
        assert not (tmp_path / rel).exists()


def test_write_repo_file_rejects_traversal(tmp_path: Path) -> None:
    write = make_write_repo_file_tool(tmp_path)
    outside_target = tmp_path.parent / "evil.txt"

    result = write("../evil.txt", "boom")
    assert result.startswith("write_repo_file:")
    assert ".." in result or "escape" in result.lower()
    assert not outside_target.exists()


def test_write_repo_file_rejects_empty_path(tmp_path: Path) -> None:
    write = make_write_repo_file_tool(tmp_path)
    assert write("", "x").startswith("write_repo_file:")
    assert write("   ", "x").startswith("write_repo_file:")


def test_write_repo_file_size_cap(tmp_path: Path) -> None:
    write = make_write_repo_file_tool(tmp_path)
    huge = "x" * (512_001)
    result = write("big.txt", huge)
    assert result.startswith("write_repo_file:")
    assert "too large" in result
    assert not (tmp_path / "big.txt").exists()


def test_write_repo_file_creates_parent_dirs(tmp_path: Path) -> None:
    write = make_write_repo_file_tool(tmp_path)
    result = write("a/very/deep/new/path.txt", "ok\n")
    assert result.startswith("wrote ")
    assert (tmp_path / "a/very/deep/new/path.txt").read_text() == "ok\n"


def test_apply_patch_one_line_edit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo, initial_file="hello.txt", initial_content="line1\nline2\n")
    apply = make_apply_patch_tool(repo)

    diff = (
        "diff --git a/hello.txt b/hello.txt\n"
        "--- a/hello.txt\n"
        "+++ b/hello.txt\n"
        "@@ -1,2 +1,2 @@\n"
        " line1\n"
        "-line2\n"
        "+line2-changed\n"
    )
    result = apply(diff)
    assert result.startswith("applied "), result
    assert "hello.txt" in result
    assert (repo / "hello.txt").read_text() == "line1\nline2-changed\n"


def test_apply_patch_rejects_dot_git(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    apply = make_apply_patch_tool(repo)

    diff = (
        "diff --git a/.git/config b/.git/config\n"
        "--- a/.git/config\n"
        "+++ b/.git/config\n"
        "@@ -1 +1 @@\n"
        "-x\n"
        "+y\n"
    )
    result = apply(diff)
    assert result.startswith("apply_patch:"), result
    assert ".git" in result


def test_apply_patch_rejects_traversal(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    apply = make_apply_patch_tool(repo)

    diff = (
        "diff --git a/../escape.txt b/../escape.txt\n"
        "--- a/../escape.txt\n"
        "+++ b/../escape.txt\n"
        "@@ -0,0 +1 @@\n"
        "+pwn\n"
    )
    result = apply(diff)
    assert result.startswith("apply_patch:"), result


def test_apply_patch_empty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    apply = make_apply_patch_tool(repo)

    assert apply("").startswith("apply_patch:")
    assert apply("   \n").startswith("apply_patch:")


def test_apply_patch_no_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    apply = make_apply_patch_tool(repo)

    result = apply("not a real diff\njust text\n")
    assert result.startswith("apply_patch:")


def test_apply_patch_not_a_git_repo(tmp_path: Path) -> None:
    apply = make_apply_patch_tool(tmp_path)
    diff = (
        "diff --git a/x.txt b/x.txt\n"
        "--- a/x.txt\n"
        "+++ b/x.txt\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
    )
    result = apply(diff)
    assert result.startswith("apply_patch:")
    assert "git" in result.lower()


@pytest.mark.parametrize("blocked_first", [".git", ".git/hooks/pre-commit"])
def test_dot_git_first_segment_blocked(tmp_path: Path, blocked_first: str) -> None:
    write = make_write_repo_file_tool(tmp_path)
    result = write(blocked_first, "x")
    assert result.startswith("write_repo_file:")
