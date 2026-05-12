"""Scene generation workflow: outline → design pass → implementation.

Runs on an isolated git branch (``agno/scene-generation/<UTC>``) like AuditFlow.
Each specialist commits after their run so the tree stays attributable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from agno.knowledge.protocol import KnowledgeProtocol
from agno.workflow import Workflow
from agno.workflow.step import Step
from agno.workflow.types import StepInput, StepOutput

from game_dev_crew.config import make_agent_db, repo_root
from game_dev_crew.tracing import maybe_setup_tracing
from game_dev_crew.crew.agents import build_agents
from game_dev_crew.workflow.audit_flow import _commit_agent_writes, _iter_nested_step_outputs, _run_output_text
from game_dev_crew.workflow.git_isolation import create_audit_branch

_RUN_LABEL = "scene-generation"
_SCENE_GEN_SILENT_DUNGEON_HINT = (
    "When **REPO_ROOT** is *Silent Dungeon* / **Calvário** (e.g. `src/campaigns/calvario/` exists), "
    "align batches with that tree and authoritative contracts under `src/engine/schema/`; "
    "if `REPO_ROOT/.cursor/skills/create-scenes/SKILL.md` exists, follow it—still verify with "
    "`glob` / `read_repo_file` on the live tree."
)


def _prior_context(step_input: StepInput, limit: int = 12000) -> str:
    if hasattr(step_input, "get_all_previous_content"):
        return (step_input.get_all_previous_content() or "")[:limit]
    return ""


def make_scene_generation_executors(
    repo_root_path: Path, game_knowledge: Optional[KnowledgeProtocol] = None
):
    agents = build_agents(repo_root_path, game_knowledge=game_knowledge)
    root = repo_root_path.resolve()

    def storytelling_outline(step_input: StepInput, session_state: dict[str, Any]) -> StepOutput:
        session_state.setdefault("scene_gen_outputs", {})
        session_state.setdefault("changed_files", [])
        session_state.setdefault("scene_gen_committed_by_agent", {})
        committed = session_state["scene_gen_committed_by_agent"]
        raw = step_input.get_input_as_string() or ""
        prior = _prior_context(step_input)
        blocks = [
            "## Goal: new campaign scenes\n" + raw.strip(),
            "Propose a concrete batch: scene IDs (English), filenames under "
            "`src/campaigns/<campaign>/scenes/`, beats, branching, and PT-BR tone. "
            "Use `glob` / `read_repo_file` to align with the existing campaign tree.",
            _SCENE_GEN_SILENT_DUNGEON_HINT,
        ]
        if prior:
            blocks.append("## Prior workflow steps\n" + prior)
        msg = "\n\n".join(blocks)
        ro = agents["storytelling"].run(msg)
        text = _run_output_text(ro)
        session_state["scene_gen_outputs"]["storytelling"] = text
        _commit_agent_writes(root, 0, "storytelling", session_state, committed, run_label=_RUN_LABEL)
        payload = {
            "step": "storytelling_outline",
            "markdown": text,
            "committed_by_agent": dict(committed),
        }
        return StepOutput(
            step_name="storytelling_outline",
            step_type="Step",
            content=json.dumps(payload, ensure_ascii=False),
            success=True,
        )

    def game_design_pass(step_input: StepInput, session_state: dict[str, Any]) -> StepOutput:
        committed = session_state.setdefault("scene_gen_committed_by_agent", {})
        story = str(session_state.get("scene_gen_outputs", {}).get("storytelling", ""))
        raw = step_input.get_input_as_string() or ""
        prior = _prior_context(step_input)
        msg = "\n\n".join(
            [
                "## User brief\n" + raw.strip(),
                "## Storytelling outline\n```\n" + story[:20000] + "\n```",
                "Review mechanics, progression, and engine/schema fit. "
                "Call out risks; use repo tools to verify how choices map to engine types.",
                _SCENE_GEN_SILENT_DUNGEON_HINT,
            ]
            + ([f"## Prior steps\n{prior}"] if prior else []),
        )
        ro = agents["game_design"].run(msg)
        text = _run_output_text(ro)
        session_state["scene_gen_outputs"]["game_design"] = text
        _commit_agent_writes(root, 1, "game_design", session_state, committed, run_label=_RUN_LABEL)
        payload = {
            "step": "game_design_pass",
            "markdown": text,
            "committed_by_agent": dict(committed),
        }
        return StepOutput(
            step_name="game_design_pass",
            step_type="Step",
            content=json.dumps(payload, ensure_ascii=False),
            success=True,
        )

    def senior_implement(step_input: StepInput, session_state: dict[str, Any]) -> StepOutput:
        committed = session_state.setdefault("scene_gen_committed_by_agent", {})
        out = session_state.setdefault("scene_gen_outputs", {})
        raw = step_input.get_input_as_string() or ""
        prior = _prior_context(step_input)
        msg = "\n\n".join(
            [
                "## User brief\n" + raw.strip(),
                "## Storytelling\n```\n" + str(out.get("storytelling", ""))[:16000] + "\n```",
                "## Game design\n```\n" + str(out.get("game_design", ""))[:16000] + "\n```",
                "Implement the new scenes: create or edit markdown + YAML under the campaign "
                "`scenes/` tree using `write_repo_file` / `apply_patch`. "
                "After edits, run `npm run test` and, if scenes changed, `run_validate_scenes`.",
                _SCENE_GEN_SILENT_DUNGEON_HINT,
            ]
            + ([f"## Prior steps\n{prior}"] if prior else []),
        )
        ro = agents["senior_developer"].run(msg)
        text = _run_output_text(ro)
        session_state["scene_gen_outputs"]["senior_developer"] = text
        _commit_agent_writes(root, 2, "senior_developer", session_state, committed, run_label=_RUN_LABEL)
        payload = {
            "step": "senior_implement",
            "markdown": text,
            "committed_by_agent": dict(committed),
            "changed_files": list(session_state.get("changed_files", [])),
        }
        return StepOutput(
            step_name="senior_implement",
            step_type="Step",
            content=json.dumps(payload, ensure_ascii=False),
            success=True,
        )

    return storytelling_outline, game_design_pass, senior_implement


def build_scene_generation_workflow(
    repo_root_arg: Path | None = None,
    db: Any | None = None,
    game_knowledge: Optional[KnowledgeProtocol] = None,
) -> Workflow:
    root = (repo_root_arg or repo_root()).resolve()
    s1, s2, s3 = make_scene_generation_executors(root, game_knowledge=game_knowledge)
    wf_db = make_agent_db() if db is None else db
    wf_kw: dict[str, Any] = {}
    if wf_db is not None:
        wf_kw["db"] = wf_db
        wf_kw["add_workflow_history_to_steps"] = True
        wf_kw["num_history_runs"] = 3
    return Workflow(
        id="scene-generation",
        name="Scene generation",
        description="Storytelling outline → game design review → senior developer implements scenes",
        **wf_kw,
        steps=[
            Step(
                name="storytelling_outline",
                executor=s1,
                description="Outline new scene batch aligned with the campaign tree",
            ),
            Step(
                name="game_design_pass",
                executor=s2,
                description="Mechanics and schema alignment for the proposed scenes",
            ),
            Step(
                name="senior_implement",
                executor=s3,
                description="Apply scene files and run tests / validate:scenes when needed",
            ),
        ],
    )


def format_scene_generation_cli_report(workflow_run: Any) -> str:
    """Human-readable summary of all scene-generation steps."""
    parts: list[str] = []
    for step in _iter_nested_step_outputs(getattr(workflow_run, "step_results", None)):
        name = getattr(step, "step_name", None) or ""
        raw = step.content
        if not isinstance(raw, str):
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            parts.append(f"### {name}\n{raw}")
            continue
        meta = {k: v for k, v in data.items() if k != "markdown"}
        parts.append(
            f"### {name}\n{json.dumps(meta, indent=2, ensure_ascii=False)}\n--- markdown ---\n{data.get('markdown', '')}"
        )
    return "\n\n".join(parts) if parts else str(getattr(workflow_run, "content", workflow_run) or "(no step output)")


def run_scene_generation_flow(
    user_prompt: str,
    *,
    repo_root_arg: Path | None = None,
    session_state: dict[str, Any] | None = None,
    game_knowledge: Optional[KnowledgeProtocol] = None,
) -> Any:
    """Run Scene generation synchronously; returns workflow run output."""
    maybe_setup_tracing(make_agent_db())
    root = (repo_root_arg or repo_root()).resolve()
    state = session_state if session_state is not None else {}
    if not state.get("scene_gen_branch"):
        state["scene_gen_branch"] = create_audit_branch(root, prefix="agno/scene-generation")
    wf = build_scene_generation_workflow(repo_root_arg=root, game_knowledge=game_knowledge)
    return wf.run(input=user_prompt, session_state=state, add_session_state_to_context=True)
