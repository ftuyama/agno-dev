"""Registry helpers for SQLite-serialized workflows."""

from pathlib import Path

from agno.db.sqlite import SqliteDb
from agno.registry import Registry
from agno.workflow.workflow import get_workflows

from game_dev_crew.workflow.audit_flow import build_audit_workflow
from game_dev_crew.workflow.registry_functions import collect_workflow_functions_for_registry
from game_dev_crew.workflow.scene_generation_flow import build_scene_generation_workflow


def test_collect_workflow_functions_covers_serialized_executor_refs(tmp_path: Path) -> None:
    root = tmp_path
    wf_audit = build_audit_workflow(repo_root_arg=root, db=None)
    wf_scene = build_scene_generation_workflow(repo_root_arg=root, db=None)
    funcs = collect_workflow_functions_for_registry([wf_audit, wf_scene])
    names = {f.__name__ for f in funcs}
    assert "end_loop_on_approval" in names
    assert "audit_iteration" in names
    assert "storytelling_outline" in names
    assert "game_design_pass" in names
    assert "senior_implement" in names


def test_get_workflows_rehydrates_with_registry_functions(tmp_path: Path) -> None:
    """Same shape as AgentOS: save workflows, then load via get_workflows + Registry."""
    db = SqliteDb(db_file=str(tmp_path / "wf_registry_test.sqlite"))
    init = getattr(db, "_create_all_tables", None)
    if callable(init):
        init()
    root = tmp_path
    workflows = [
        build_audit_workflow(repo_root_arg=root, db=db),
        build_scene_generation_workflow(repo_root_arg=root, db=db),
    ]
    for wf in workflows:
        wf.save()
    reg = Registry()
    reg.functions.extend(collect_workflow_functions_for_registry(workflows))
    loaded = get_workflows(db=db, registry=reg)
    assert len(loaded) >= 2
    ids = {w.id for w in loaded}
    assert "audit-flow" in ids
    assert "scene-generation" in ids
