"""Persist code-defined agents, teams, and workflows into Agno's component store (SQLite).

Each ``component.save()`` in Agno appends a brand-new ``published`` row to
``agno_component_configs`` — running ``serve`` / ``sync-components`` repeatedly was bloating
that table by one version per component per startup. We now serialize each component once,
compare its hash against the latest stored config, and only call ``save()`` when something
actually changed.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from agno.db.base import BaseDb

from game_dev_crew.config import make_agent_db

if TYPE_CHECKING:
    from agno.agent import Agent
    from agno.team import Team
    from agno.workflow.workflow import Workflow

_LOG = logging.getLogger(__name__)

_VOLATILE_KEYS: frozenset[str] = frozenset({"step_id"})


def _strip_volatile(value: Any) -> Any:
    """Recursively drop keys that change every process even when the config is logically the same.

    ``Workflow.to_dict()`` assigns a fresh UUID to ``step_id`` on every construction, which would
    otherwise make the signature differ on every startup. Extend ``_VOLATILE_KEYS`` if other
    auto-generated fields show up.
    """
    if isinstance(value, dict):
        return {k: _strip_volatile(v) for k, v in value.items() if k not in _VOLATILE_KEYS}
    if isinstance(value, list):
        return [_strip_volatile(v) for v in value]
    return value


def _config_signature(config: Any) -> str:
    """Stable sha256 over the serialized config — order-insensitive, ignoring volatile keys."""
    payload = json.dumps(_strip_volatile(config), sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _save_if_changed(component: Any, db: BaseDb, kind: str) -> bool:
    """Call ``component.save()`` only when its serialized config differs from the latest stored.

    Returns ``True`` if a new version was written, ``False`` if the existing config already
    matches (and we therefore skipped the round-trip).
    """
    component_id = getattr(component, "id", None)
    if not component_id:
        component.save()
        return True

    new_config = component.to_dict()
    new_sig = _config_signature(new_config)
    try:
        stored = db.get_config(component_id=component_id)
    except Exception as exc:  # noqa: BLE001 — first run or schema not ready yet
        _LOG.debug("get_config(%s) failed: %s; falling back to save.", component_id, exc)
        stored = None

    stored_config = stored.get("config") if stored else None
    if stored_config is not None and _config_signature(stored_config) == new_sig:
        _LOG.debug(
            "%s %s already in sync (config v%s); skipping save.",
            kind,
            component_id,
            stored.get("version"),
        )
        return False

    component.save()
    return True


def persist_code_defined_components(
    repo_root: Path,
    *,
    db: Optional[BaseDb] = None,
    agents: Optional[Sequence["Agent"]] = None,
    teams: Optional[Sequence["Team"]] = None,
    workflow: Optional["Workflow"] = None,
    workflows: Optional[Sequence["Workflow"]] = None,
) -> bool:
    """Write agents, teams, and workflow(s) into ``SqliteDb`` (Studio / component configs).

    Prefer passing ``db`` plus the same ``agents`` / ``teams`` instances the app serves, so the
    DB matches runtime (e.g. Auditor with knowledge).

    If ``workflows`` is set, each workflow is saved. Else if ``workflow`` is set, only that one.
    Otherwise saves AuditFlow and Scene generation defaults.

    Each component is saved only when its serialized config changed since the last published
    version — keeps ``agno_component_configs`` from growing one row per startup.

    Returns ``True`` if the persistence pass ran (regardless of how many components actually
    changed), ``False`` if there is no sync ``BaseDb`` (memory DB off).
    """
    from game_dev_crew.crew.agents import build_agents
    from game_dev_crew.crew.teams import build_game_dev_crew_team, build_specialists_team
    from game_dev_crew.workflow.audit_flow import build_audit_workflow
    from game_dev_crew.workflow.scene_generation_flow import build_scene_generation_workflow

    db_ = db if db is not None else make_agent_db()
    if db_ is None or not isinstance(db_, BaseDb):
        return False

    init = getattr(db_, "_create_all_tables", None)
    if callable(init):
        init()

    root = repo_root.resolve()

    saved = {"agent": 0, "team": 0, "workflow": 0}
    seen = {"agent": 0, "team": 0, "workflow": 0}

    agent_iter = agents if agents is not None else build_agents(root).values()
    for agent in agent_iter:
        seen["agent"] += 1
        if _save_if_changed(agent, db_, "agent"):
            saved["agent"] += 1

    team_iter = teams if teams is not None else (build_specialists_team(root), build_game_dev_crew_team(root))
    for team in team_iter:
        seen["team"] += 1
        if _save_if_changed(team, db_, "team"):
            saved["team"] += 1

    if workflows is not None:
        wf_list = list(workflows)
    elif workflow is not None:
        wf_list = [workflow]
    else:
        wf_list = [
            build_audit_workflow(repo_root_arg=root),
            build_scene_generation_workflow(repo_root_arg=root),
        ]
    for wf in wf_list:
        if wf.db is None:
            continue
        seen["workflow"] += 1
        if _save_if_changed(wf, db_, "workflow"):
            saved["workflow"] += 1

    _LOG.info(
        "Component sync: agents %d/%d, teams %d/%d, workflows %d/%d (changed/total).",
        saved["agent"], seen["agent"],
        saved["team"], seen["team"],
        saved["workflow"], seen["workflow"],
    )
    return True
