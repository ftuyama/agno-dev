"""AgentOS ``GET /workflows`` should not duplicate code-defined workflows persisted to SQLite."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import game_dev_crew.config as config_mod


@pytest.fixture
def minimal_game_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "game"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"t","scripts":{}}\n')
    return repo


def test_workflows_list_unique_ids_with_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    minimal_game_repo: Path,
) -> None:
    monkeypatch.setattr(config_mod, "_agent_db_instance", None)
    monkeypatch.setattr(config_mod, "_agent_db_fingerprint", None)
    monkeypatch.setenv("REPO_ROOT", str(minimal_game_repo))
    monkeypatch.setenv("AGNO_MEMORY_SQLITE_PATH", str(tmp_path / "workflows_list.sqlite"))
    monkeypatch.setenv("AGNO_MEMORY_DB", "sqlite")
    monkeypatch.setenv("AGNO_TRACING", "off")

    from game_dev_crew.agent_os_app import build_app

    app = build_app()
    r = TestClient(app).get("/workflows")
    assert r.status_code == 200
    data = r.json()
    ids = [item["id"] for item in data]
    assert len(ids) == len(set(ids)), f"duplicate workflow ids: {ids}"
