"""AgentOS-visible Knowledge (RAG) for Studio and the Auditor agent."""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from game_dev_crew.config import load_env

_LOG = logging.getLogger(__name__)

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
    version: int = 1


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


def _file_fingerprint(path: Path) -> str:
    """First 12 chars of sha256(file bytes); changes whenever the seed file changes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _expected_content_hash(name: str, description: str, path: Path) -> str:
    """Mirror of ``Knowledge._build_content_hash`` for the (name, description, path) case.

    Kept in sync with agno/knowledge/knowledge.py — used only as a cheap pre-check
    so we can skip ``Knowledge.insert`` when the seed is already up to date.
    """
    return hashlib.sha256(":".join([name, description, str(path)]).encode()).hexdigest()


def seed_default_knowledge(knowledge: "Knowledge") -> None:
    """Index packaged seed markdown only when the seed (file or version) actually changed.

    Each seed gets a revision marker — ``[rev v{spec.version}-{file_fingerprint}]`` — appended
    to its description. The marker participates in Agno's ``content_hash`` so:

    * unchanged file + unchanged ``spec.version`` → ``skip_if_exists=True`` short-circuits
      and we avoid the re-embed loop seen in the startup logs;
    * file edit OR ``spec.version`` bump → revision marker changes, hash differs, we delete
      stale vectors for that ``seed_id`` and re-insert exactly once.
    """
    vector_db = getattr(knowledge, "vector_db", None)
    content_hash_exists = getattr(vector_db, "content_hash_exists", None)

    for spec in _SEED_DOCS:
        path = _SEED_DIR / spec.filename
        if not path.is_file():
            continue

        revision = f"v{spec.version}-{_file_fingerprint(path)}"
        description = f"{spec.description} [rev {revision}]"
        seed_id = spec.metadata.get("seed_id")

        if callable(content_hash_exists) and content_hash_exists(
            _expected_content_hash(spec.title, description, path)
        ):
            _LOG.debug("Knowledge seed %s already up to date (rev %s); skipping.", seed_id, revision)
            continue

        if seed_id:
            try:
                knowledge.remove_vectors_by_metadata({"seed_id": seed_id})
            except Exception as exc:  # noqa: BLE001 — best-effort cleanup of orphan revs
                _LOG.debug("Could not prune stale vectors for seed %s: %s", seed_id, exc)

        knowledge.insert(
            name=spec.title,
            description=description,
            path=str(path),
            metadata={**spec.metadata, "rev": revision},
            upsert=True,
            skip_if_exists=True,
        )
