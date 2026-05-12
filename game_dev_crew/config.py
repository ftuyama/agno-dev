"""Environment, repo paths, instruction loading, and OpenRouter model."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from agno.models.openrouter import OpenRouter
from dotenv import load_dotenv

if TYPE_CHECKING:
    from agno.db.base import BaseDb

_CREW_PKG = Path(__file__).resolve().parent
_AGNO_DIR = _CREW_PKG.parent
_INSTRUCTIONS_DIR = _CREW_PKG / "instructions"

# Lazily created Agno session + user-memory store (one shared instance per process).
_agent_db_instance: Optional["BaseDb"] = None
_agent_db_fingerprint: Optional[str] = None


def load_env() -> None:
    load_dotenv(_AGNO_DIR / ".env", override=False)


def repo_root() -> Path:
    """Game / target repository root when ``REPO_ROOT`` is set; else this project root."""
    load_env()
    raw = os.environ.get("REPO_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _AGNO_DIR.resolve()


def openrouter_model_id() -> str:
    load_env()
    return os.environ.get("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"


def make_model() -> OpenRouter:
    return OpenRouter(id=openrouter_model_id())


def audit_flow_max_iterations() -> int:
    load_env()
    try:
        return max(1, int(os.environ.get("AUDIT_FLOW_MAX_ITERATIONS", "4")))
    except ValueError:
        return 4


def tracing_enabled() -> bool:
    """When true, call ``agno.tracing.setup_tracing`` so runs export spans to the Agno DB (requires SQLite)."""
    load_env()
    raw = os.environ.get("AGNO_TRACING", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    mem = os.environ.get("AGNO_MEMORY_DB", "").strip().lower()
    if mem in ("none", "off", "false", "0"):
        return False
    return True


def validate_scenes_tool_enabled() -> bool:
    load_env()
    return os.environ.get("ENABLE_VALIDATE_SCENES_TOOL", "").lower() in ("1", "true", "yes")


def repo_shell_tools_enabled() -> bool:
    """When true, Auditor/Senior get ``execute_command`` and ``bash`` (allowlisted npm only)."""
    load_env()
    return os.environ.get("ENABLE_REPO_SHELL_TOOLS", "true").lower() in ("1", "true", "yes")


def _sqlite_memory_db_path() -> Path:
    load_env()
    raw = os.environ.get("AGNO_MEMORY_SQLITE_PATH", "").strip()
    db_path = Path(raw).expanduser() if raw else _AGNO_DIR / ".agno_memory.sqlite"
    return db_path.resolve()


def memory_sqlite_file() -> Path:
    """Resolved path of the main Agno SQLite file (``AGNO_MEMORY_SQLITE_PATH`` or project default)."""
    return _sqlite_memory_db_path()


def make_agent_db() -> Optional["BaseDb"]:
    """Shared Agno SQLite ``BaseDb`` for sessions, memories, workflows, and AgentOS Studio.

    When ``AGNO_MEMORY_DB`` is unset or ``sqlite`` (default), uses ``.agno_memory.sqlite`` under
    the project root unless ``AGNO_MEMORY_SQLITE_PATH`` is set. Set ``AGNO_MEMORY_DB`` to
    ``none`` / ``off`` / ``false`` / ``0`` to disable persistence entirely.
    """
    global _agent_db_instance, _agent_db_fingerprint
    load_env()
    raw = os.environ.get("AGNO_MEMORY_DB", "").strip().lower()
    if raw in ("none", "off", "false", "0"):
        return None
    if raw in ("", "sqlite"):
        pass  # default + explicit sqlite
    else:
        raise ValueError(
            "Invalid AGNO_MEMORY_DB={!r}; use none or sqlite (see .env.example).".format(raw)
        )
    fp = str(_sqlite_memory_db_path())
    if _agent_db_instance is not None and _agent_db_fingerprint == fp:
        return _agent_db_instance
    from agno.db.sqlite import SqliteDb

    db_path = Path(fp)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = SqliteDb(db_file=str(db_path))
    _agent_db_instance = db
    _agent_db_fingerprint = fp
    return db


def load_instruction(name: str) -> str:
    path = _INSTRUCTIONS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Missing instruction file: {path}")
    return path.read_text(encoding="utf-8")
