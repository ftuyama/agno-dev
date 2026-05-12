"""AgentOS-visible Knowledge (RAG) for Studio and the Auditor agent."""

from __future__ import annotations

import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from game_dev_crew.config import load_env

if TYPE_CHECKING:
    from agno.db.base import BaseDb
    from agno.knowledge.knowledge import Knowledge

_CREW_PKG = Path(__file__).resolve().parent
_AGNO_DIR = _CREW_PKG.parent
_SEED_DIR = _CREW_PKG / "knowledge_seed"
KNOWLEDGE_NAME = "Game Dev Crew KB"
LANCEDB_TABLE = "game_dev_crew_kb"

_DISABLE_VALUES = frozenset({"none", "off", "false", "0"})


def _knowledge_enabled() -> bool:
    load_env()
    return os.environ.get("AGNO_KNOWLEDGE", "").strip().lower() not in _DISABLE_VALUES


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

    Returns ``None`` (with a warning) if ``fastembed`` or ``lancedb`` is missing in the active
    Python — this is the silent failure mode that previously made Studio show "No instance found"
    when the entry point was launched from a Python without these deps.
    """
    if not _knowledge_enabled():
        return None
    try:
        from agno.knowledge import Knowledge
        from agno.knowledge.embedder.fastembed import FastEmbedEmbedder
        from agno.vectordb.lancedb import LanceDb
    except ImportError as exc:
        warnings.warn(
            f"Knowledge disabled: missing dependency ({exc}). "
            f"Install with: {sys.executable} -m pip install fastembed lancedb",
            RuntimeWarning,
            stacklevel=2,
        )
        return None

    return Knowledge(
        name=KNOWLEDGE_NAME,
        description="Crew overview, Silent Dungeon premise/scene/mechanics seeds, and AgentOS Knowledge + Auditor search.",
        vector_db=LanceDb(
            uri=str(_lancedb_dir()),
            table_name=LANCEDB_TABLE,
            embedder=FastEmbedEmbedder(),
        ),
        contents_db=_contents_db_for_knowledge(agent_db),
        max_results=8,
    )


@dataclass(frozen=True)
class _SeedDoc:
    filename: str
    title: str
    description: str
    metadata: dict[str, Any]


_SEED_DOCS: tuple[_SeedDoc, ...] = (
    _SeedDoc(
        "crew_overview.md",
        "Game Dev Crew — overview",
        "Crew roles (Auditor, specialists, senior, reviewer), AuditFlow loop, REPO_ROOT conventions, "
        "and how this KB is used in AgentOS Studio and optional Auditor RAG.",
        {
            "seed_id": "crew_overview",
            "kind": "crew_onboarding",
            "content_language": "en",
        },
    ),
    _SeedDoc(
        "silent_dungeon_premise.md",
        "Silent Dungeon — premise (seed)",
        "Pitch, tone, EN vs PT-BR split for IDs vs player copy, content warning, and where authoritative "
        "game schema lives under REPO_ROOT.",
        {
            "seed_id": "silent_dungeon_premise",
            "kind": "game_seed",
            "game": "silent_dungeon",
            "content_language": "en",
        },
    ),
    _SeedDoc(
        "silent_dungeon_scene_workflow.md",
        "Silent Dungeon — scene workflow (seed)",
        "Scene layout under calvario, schema authority, branching/choices, and npm validation hooks; "
        "points agents at REPO_ROOT tools for ground truth.",
        {
            "seed_id": "silent_dungeon_scene_workflow",
            "kind": "game_seed",
            "game": "silent_dungeon",
            "content_language": "en",
        },
    ),
    _SeedDoc(
        "silent_dungeon_world_and_mechanics.md",
        "Silent Dungeon — world & mechanics (seed)",
        "Campaign acts, mechanics summary, and PT-BR support text; always subordinate to "
        "REPO_ROOT/src/engine/schema and combat code.",
        {
            "seed_id": "silent_dungeon_world_and_mechanics",
            "kind": "game_seed",
            "game": "silent_dungeon",
            "content_language": "mixed",
        },
    ),
)


def seed_default_knowledge(knowledge: "Knowledge") -> None:
    """Index packaged seed markdown with per-document name, description, and metadata for Studio."""
    for spec in _SEED_DOCS:
        path = _SEED_DIR / spec.filename
        if not path.is_file():
            continue
        knowledge.insert(
            name=spec.title,
            description=spec.description,
            path=str(path),
            metadata=spec.metadata,
            upsert=True,
            skip_if_exists=False,
        )
