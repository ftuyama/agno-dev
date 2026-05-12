"""Integration-style test for the AuditFlow write-commit-verify loop.

Replaces the real Agno agents with stub objects whose ``run`` callbacks write
files into a tmp git repo, then drives one iteration of the executor and
checks that each writing agent produced its own commit on the audit branch.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from game_dev_crew.workflow import audit_flow as audit_flow_mod


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=os.fspath(repo),
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "package.json").write_text('{"name":"x","scripts":{}}\n')
    _git(repo, "add", "package.json")
    _git(repo, "commit", "-m", "init")
    _git(repo, "checkout", "-b", "agno/audit-flow/test")


class _FakeRunOutput:
    def __init__(self, text: str) -> None:
        self.content = text

    def get_content_as_string(self) -> str:
        return self.content


class _FakeAgent:
    """Stand-in for an Agno ``Agent`` with a scripted ``run`` callback."""

    def __init__(self, *, text: str, side_effect=None) -> None:
        self._text = text
        self._side_effect = side_effect
        self.run_count = 0
        self.last_msg: str | None = None

    def run(self, msg: str, *args, **kwargs) -> _FakeRunOutput:
        self.run_count += 1
        self.last_msg = msg
        if self._side_effect is not None:
            self._side_effect()
        return _FakeRunOutput(self._text)


class _FakeStepInput:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_input_as_string(self) -> str:
        return self._text

    def get_all_previous_content(self) -> str:
        return ""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "silent-dungeon"
    _init_repo(r)
    return r


def test_iteration_commits_per_writing_agent_and_envelope_contains_metadata(
    monkeypatch: pytest.MonkeyPatch, repo: Path
) -> None:
    def write_scene() -> None:
        target = repo / "src" / "campaigns" / "calvario" / "scenes" / "x.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("---\nid: x\n---\nA scene\n")

    def write_engine() -> None:
        target = repo / "src" / "engine" / "tuning.ts"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("export const X = 1;\n")

    fake_agents = {
        "auditor": _FakeAgent(text="findings: ok"),
        "storytelling": _FakeAgent(text="rewrote x", side_effect=write_scene),
        "ui_ux": _FakeAgent(text="no ui changes"),
        "game_design": _FakeAgent(text="no design changes"),
        "senior_developer": _FakeAgent(text="applied tuning", side_effect=write_engine),
        "reviewer": _FakeAgent(text="- ✅ all good\nSTATUS: APPROVED\n"),
    }
    monkeypatch.setattr(
        audit_flow_mod, "build_agents", lambda *a, **kw: fake_agents
    )

    executor = audit_flow_mod.make_audit_iteration_executor(repo, max_iterations=2)

    session_state: dict = {"audit_branch": "agno/audit-flow/test"}
    step_in = _FakeStepInput("audit calvario campaign")

    out = executor(step_in, session_state)

    payload = json.loads(out.content)
    assert payload["approved"] is True
    assert payload["stop_loop"] is True
    assert payload["audit_branch"] == "agno/audit-flow/test"

    by = payload["committed_by_agent"]
    assert set(by) == {"storytelling", "senior_developer"}
    assert "src/campaigns/calvario/scenes/x.md" in by["storytelling"]["files"]
    assert "src/engine/tuning.ts" in by["senior_developer"]["files"]
    assert len(by["storytelling"]["sha"]) == 40
    assert by["storytelling"]["sha"] != by["senior_developer"]["sha"]

    assert set(payload["committed_files"]) == {
        "src/campaigns/calvario/scenes/x.md",
        "src/engine/tuning.ts",
    }
    assert set(session_state["changed_files"]) == set(payload["committed_files"])

    log = _git(repo, "log", "--pretty=%s", "-3").stdout.strip().splitlines()
    assert "[audit-flow iter 0] storytelling" in log
    assert "[audit-flow iter 0] senior_developer" in log

    reviewer_msg = fake_agents["reviewer"].last_msg
    assert reviewer_msg is not None
    assert "Patched files this iteration" in reviewer_msg
    assert "src/campaigns/calvario/scenes/x.md (by storytelling)" in reviewer_msg
    assert "src/engine/tuning.ts (by senior_developer)" in reviewer_msg
    assert "Verification expected" in reviewer_msg


def test_iteration_with_no_writes_produces_no_commits(
    monkeypatch: pytest.MonkeyPatch, repo: Path
) -> None:
    fake_agents = {
        "auditor": _FakeAgent(text="no findings"),
        "storytelling": _FakeAgent(text="no story changes"),
        "ui_ux": _FakeAgent(text="no ui"),
        "game_design": _FakeAgent(text="no design"),
        "senior_developer": _FakeAgent(text="nothing to patch"),
        "reviewer": _FakeAgent(text="STATUS: APPROVED\n"),
    }
    monkeypatch.setattr(
        audit_flow_mod, "build_agents", lambda *a, **kw: fake_agents
    )

    executor = audit_flow_mod.make_audit_iteration_executor(repo, max_iterations=2)
    session_state: dict = {"audit_branch": "agno/audit-flow/test"}

    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    out = executor(_FakeStepInput("scope"), session_state)
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()

    payload = json.loads(out.content)
    assert payload["committed_by_agent"] == {}
    assert payload["committed_files"] == []
    assert head_before == head_after


def test_iteration_records_changed_files_cumulatively(
    monkeypatch: pytest.MonkeyPatch, repo: Path
) -> None:
    counter = {"n": 0}

    def write_unique() -> None:
        counter["n"] += 1
        target = repo / f"docs/note-{counter['n']}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"note {counter['n']}\n")

    fake_agents = {
        "auditor": _FakeAgent(text="ok", side_effect=write_unique),
        "storytelling": _FakeAgent(text="ok"),
        "ui_ux": _FakeAgent(text="ok"),
        "game_design": _FakeAgent(text="ok"),
        "senior_developer": _FakeAgent(text="ok", side_effect=write_unique),
        "reviewer": _FakeAgent(text="STATUS: APPROVED\n"),
    }
    monkeypatch.setattr(
        audit_flow_mod, "build_agents", lambda *a, **kw: fake_agents
    )

    executor = audit_flow_mod.make_audit_iteration_executor(repo, max_iterations=2)
    session_state: dict = {"audit_branch": "agno/audit-flow/test"}

    executor(_FakeStepInput("scope"), session_state)

    assert set(session_state["changed_files"]) == {"docs/note-1.md", "docs/note-2.md"}
