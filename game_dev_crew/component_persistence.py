"""Persist code-defined agents, teams, and workflows into Agno's component store (SQLite)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from agno.db.base import BaseDb

from game_dev_crew.config import make_agent_db

if TYPE_CHECKING:
    from agno.agent import Agent
    from agno.team import Team
    from agno.workflow.workflow import Workflow


def persist_code_defined_components(
    repo_root: Path,
    *,
    db: Optional[BaseDb] = None,
    agents: Optional[Sequence["Agent"]] = None,
    teams: Optional[Sequence["Team"]] = None,
    workflow: Optional["Workflow"] = None,
) -> bool:
    """Write agents, teams, and workflow into ``SqliteDb`` (Studio / component configs).

    Prefer passing ``db`` plus the same ``agents`` / ``teams`` instances the app serves, so the
    DB matches runtime (e.g. Auditor with knowledge).

    Returns ``True`` if saves ran, ``False`` if there is no sync ``BaseDb`` (memory DB off).
    """
    from game_dev_crew.crew.agents import build_agents
    from game_dev_crew.crew.teams import build_game_dev_crew_team, build_specialists_team
    from game_dev_crew.workflow.audit_flow import build_audit_workflow

    db_ = db if db is not None else make_agent_db()
    if db_ is None or not isinstance(db_, BaseDb):
        return False

    init = getattr(db_, "_create_all_tables", None)
    if callable(init):
        init()

    root = repo_root.resolve()

    agent_iter = agents if agents is not None else build_agents(root).values()
    for agent in agent_iter:
        agent.save()

    if teams is not None:
        for team in teams:
            team.save()
    else:
        build_specialists_team(root).save()
        build_game_dev_crew_team(root).save()

    wf = workflow if workflow is not None else build_audit_workflow(repo_root_arg=root)
    if wf.db is not None:
        wf.save()

    return True
