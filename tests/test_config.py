"""Tests for config helpers (env-driven, no network)."""

from __future__ import annotations

import pytest

from game_dev_crew import config as config_mod


@pytest.fixture(autouse=True)
def clear_agent_db_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid leaking SqliteDb between tests if make_agent_db is ever used."""
    monkeypatch.setattr(config_mod, "_agent_db_instance", None)
    monkeypatch.setattr(config_mod, "_agent_db_fingerprint", None)


@pytest.fixture(autouse=True)
def skip_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Config helpers call load_env(); avoid project .env overriding monkeypatched os.environ."""
    monkeypatch.setattr(config_mod, "load_env", lambda: None)


def test_audit_flow_max_iterations_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDIT_FLOW_MAX_ITERATIONS", raising=False)
    assert config_mod.audit_flow_max_iterations() == 4


def test_audit_flow_max_iterations_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_FLOW_MAX_ITERATIONS", "7")
    assert config_mod.audit_flow_max_iterations() == 7


def test_audit_flow_max_iterations_invalid_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_FLOW_MAX_ITERATIONS", "not-a-number")
    assert config_mod.audit_flow_max_iterations() == 4


def test_audit_flow_max_iterations_minimum_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_FLOW_MAX_ITERATIONS", "0")
    assert config_mod.audit_flow_max_iterations() == 1


@pytest.mark.parametrize(
    ("tracing", "memory_db", "expected"),
    [
        ("off", "", False),
        ("on", "", True),
        ("", "none", False),
        ("", "", True),
    ],
)
def test_tracing_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tracing: str,
    memory_db: str,
    expected: bool,
) -> None:
    if tracing:
        monkeypatch.setenv("AGNO_TRACING", tracing)
    else:
        monkeypatch.delenv("AGNO_TRACING", raising=False)
    if memory_db:
        monkeypatch.setenv("AGNO_MEMORY_DB", memory_db)
    else:
        monkeypatch.delenv("AGNO_MEMORY_DB", raising=False)
    assert config_mod.tracing_enabled() is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", False),
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("false", False),
    ],
)
def test_validate_scenes_tool_enabled(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
    expected: bool,
) -> None:
    if raw:
        monkeypatch.setenv("ENABLE_VALIDATE_SCENES_TOOL", raw)
    else:
        monkeypatch.delenv("ENABLE_VALIDATE_SCENES_TOOL", raising=False)
    assert config_mod.validate_scenes_tool_enabled() is expected
