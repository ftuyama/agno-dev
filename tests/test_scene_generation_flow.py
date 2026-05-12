"""Smoke tests for Scene generation workflow wiring."""

from __future__ import annotations

from pathlib import Path

from game_dev_crew.workflow.scene_generation_flow import (
    build_scene_generation_workflow,
    format_scene_generation_cli_report,
)


def test_build_scene_generation_workflow_has_steps_and_id(tmp_path: Path) -> None:
    wf = build_scene_generation_workflow(repo_root_arg=tmp_path, db=None)
    assert wf.id == "scene-generation"
    assert len(wf.steps) == 3


def test_format_scene_generation_cli_report_empty() -> None:
    class _Run:
        step_results = None
        content = ""

    assert "no step output" in format_scene_generation_cli_report(_Run()).lower()
