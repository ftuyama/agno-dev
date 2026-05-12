"""Tests for the AuditFlow git_isolation helpers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from game_dev_crew.workflow.git_isolation import (
    GitIsolationError,
    changed_files_in_last_commit,
    commit_after,
    create_audit_branch,
    current_branch,
    ensure_clean_tree,
    summarize_diff,
)


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=os.fspath(repo),
        capture_output=True,
        text=True,
        check=check,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("hi\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    _init_repo(r)
    return r


def test_ensure_clean_tree_passes_on_clean(repo: Path) -> None:
    ensure_clean_tree(repo)


def test_ensure_clean_tree_rejects_unstaged(repo: Path) -> None:
    (repo / "README.md").write_text("dirty\n")
    with pytest.raises(GitIsolationError) as exc:
        ensure_clean_tree(repo)
    assert "not clean" in str(exc.value)


def test_ensure_clean_tree_rejects_untracked(repo: Path) -> None:
    (repo / "newfile.txt").write_text("hello\n")
    with pytest.raises(GitIsolationError):
        ensure_clean_tree(repo)


def test_ensure_clean_tree_rejects_non_git(tmp_path: Path) -> None:
    with pytest.raises(GitIsolationError) as exc:
        ensure_clean_tree(tmp_path)
    assert "not a git repository" in str(exc.value)


def test_current_branch(repo: Path) -> None:
    assert current_branch(repo) == "main"


def test_create_audit_branch_switches(repo: Path) -> None:
    branch = create_audit_branch(repo)
    assert branch.startswith("agno/audit-flow/")
    assert current_branch(repo) == branch


def test_commit_after_returns_none_when_nothing_staged(repo: Path) -> None:
    create_audit_branch(repo)
    assert commit_after(repo, iteration_index=0, agent_id="auditor") is None


def test_commit_after_commits_unstaged_changes(repo: Path) -> None:
    create_audit_branch(repo)
    (repo / "README.md").write_text("changed\n")
    (repo / "src").mkdir()
    (repo / "src" / "new.txt").write_text("new\n")

    sha = commit_after(repo, iteration_index=2, agent_id="storytelling")
    assert sha is not None
    assert len(sha) == 40

    log = _git(repo, "log", "-1", "--pretty=%s")
    assert log.stdout.strip() == "[audit-flow iter 2] storytelling"

    changed = changed_files_in_last_commit(repo)
    assert set(changed) == {"README.md", "src/new.txt"}


def test_commit_after_commits_staged_only_changes(repo: Path) -> None:
    """``git apply --index`` stages changes; commit_after must pick those up too."""
    create_audit_branch(repo)
    (repo / "staged.txt").write_text("staged\n")
    _git(repo, "add", "staged.txt")

    sha = commit_after(repo, iteration_index=1, agent_id="senior_developer")
    assert sha is not None
    changed = changed_files_in_last_commit(repo)
    assert changed == ["staged.txt"]


def test_summarize_diff_after_commits(repo: Path) -> None:
    branch = create_audit_branch(repo)
    (repo / "a.txt").write_text("a\n")
    commit_after(repo, iteration_index=0, agent_id="auditor")

    out = summarize_diff(repo, branch, base="main")
    assert "a.txt" in out
    assert "1 file changed" in out or "1 insertion" in out


def test_summarize_diff_unknown_base_is_best_effort(repo: Path) -> None:
    branch = create_audit_branch(repo)
    out = summarize_diff(repo, branch, base="does-not-exist")
    assert "could not compute diff" in out
