"""AgentOS-visible Knowledge (RAG) for Studio and the Auditor agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from game_dev_crew.config import load_env

if TYPE_CHECKING:
    from agno.db.base import BaseDb
    from agno.knowledge.knowledge import Knowledge

_CREW_PKG = Path(__file__).resolve().parent
_AGNO_DIR = _CREW_PKG.parent
_SEED_DIR = _CREW_PKG / "knowledge_seed"


def _knowledge_enabled() -> bool:
    load_env()
    raw = os.environ.get("AGNO_KNOWLEDGE", "").strip().lower()
    if raw in ("none", "off", "false", "0"):
        return False
    return True


def _lancedb_dir() -> Path:
    d = _AGNO_DIR / ".agno_lancedb"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _contents_db_for_knowledge(agent_db: Optional["BaseDb"]) -> "BaseDb":
    if agent_db is not None:
        return agent_db
    from agno.db.sqlite import SqliteDb

    path = _AGNO_DIR / ".agno_knowledge.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteDb(db_file=str(path))


def build_game_dev_knowledge(agent_db: Optional["BaseDb"]) -> Optional["Knowledge"]:
    """Return a ``Knowledge`` instance with ``contents_db`` so AgentOS Studio lists it.

    Uses LanceDB (on-disk under ``.agno_lancedb/``) and FastEmbed (local embeddings; no API key).
    Set ``AGNO_KNOWLEDGE`` to ``none`` / ``off`` / ``false`` / ``0`` to disable.
    """
    if not _knowledge_enabled():
        return None
    try:
        from agno.knowledge import Knowledge
        from agno.knowledge.embedder.fastembed import FastEmbedEmbedder
        from agno.vectordb.lancedb import LanceDb
    except ImportError:
        return None

    contents_db = _contents_db_for_knowledge(agent_db)
    embedder = FastEmbedEmbedder()
    vector_db = LanceDb(
        uri=str(_lancedb_dir()),
        table_name="game_dev_crew_kb",
        embedder=embedder,
    )
    return Knowledge(
        name="Game Dev Crew KB",
        description="Crew overview and docs for AgentOS Knowledge + Auditor search.",
        vector_db=vector_db,
        contents_db=contents_db,
        max_results=8,
    )


def seed_default_knowledge(knowledge: "Knowledge") -> None:
    """Idempotently index packaged seed markdown into the vector store."""
    overview = _SEED_DIR / "crew_overview.md"
    if not overview.is_file():
        return
    knowledge.insert(path=str(overview), skip_if_exists=True)
