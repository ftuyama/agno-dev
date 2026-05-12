"""AuditFlow: Agno Workflow + Loop with reviewer-driven rework.

Each iteration runs the relevant agents, commits any write each one produces
on the active audit branch, and then asks the reviewer to verify the patched
tree (typically by running ``npm run test`` / ``validate:scenes``). The JSON
envelope returned by every iteration step carries the branch name plus a
``committed_by_agent`` map so the CLI can show what changed and who wrote it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator, Optional

from agno.knowledge.protocol import KnowledgeProtocol
from agno.workflow import Workflow
from agno.workflow.loop import Loop
from agno.workflow.step import Step
from agno.workflow.types import StepInput, StepOutput

from game_dev_crew.config import audit_flow_max_iterations, make_agent_db, repo_root
from game_dev_crew.tracing import maybe_setup_tracing
from game_dev_crew.crew.agents import build_agents
from game_dev_crew.workflow.git_isolation import (
    changed_files_in_last_commit,
    commit_after,
    create_audit_branch,
)
from game_dev_crew.workflow.reviewer_parse import parse_reviewer_output


def _run_output_text(run_out: Any) -> str:
    getter = getattr(run_out, "get_content_as_string", None)
    if callable(getter):
        return getter() or ""
    content = getattr(run_out, "content", None)
    return str(content) if content is not None else ""


def _iter_nested_step_outputs(obj: Any) -> Iterator[Any]:
    if obj is None:
        return
    if isinstance(obj, list):
        for item in obj:
            yield from _iter_nested_step_outputs(item)
        return
    yield obj
    for child in getattr(obj, "steps", None) or []:
        yield from _iter_nested_step_outputs(child)


def extract_audit_iteration_json(workflow_run: Any) -> dict[str, Any] | None:
    """Return the last parsed JSON payload from an ``audit_iteration`` step, if any."""
    last: dict[str, Any] | None = None
    for step in _iter_nested_step_outputs(getattr(workflow_run, "step_results", None)):
        name = getattr(step, "step_name", None)
        if name != "audit_iteration":
            continue
        raw = step.content
        if not isinstance(raw, str):
            continue
        try:
            last = json.loads(raw)
        except json.JSONDecodeError:
            continue
    return last


def format_audit_cli_report(workflow_run: Any) -> str:
    """Human-readable summary for CLI."""
    payload = extract_audit_iteration_json(workflow_run)
    if not payload:
        c = getattr(workflow_run, "content", None)
        return str(c) if c is not None else "(no step output captured)"
    parts = [
        json.dumps({k: v for k, v in payload.items() if k != "markdown_report"}, indent=2, ensure_ascii=False),
        "\n--- markdown_report ---\n",
        str(payload.get("markdown_report", "")),
    ]
    return "".join(parts)


def _commit_agent_writes(
    root: Path,
    iteration_index: int,
    agent_id: str,
    session_state: dict[str, Any],
    committed_by_agent: dict[str, dict[str, Any]],
    *,
    run_label: str = "audit-flow",
) -> None:
    """Commit any writes the just-finished agent produced; update session_state."""
    try:
        sha = commit_after(root, iteration_index, agent_id, run_label=run_label)
    except Exception as e:  # pragma: no cover - git failures are rare and surface to user
        session_state.setdefault("commit_errors", []).append(
            {"iteration": iteration_index, "agent": agent_id, "error": str(e)}
        )
        return
    if not sha:
        return
    files = changed_files_in_last_commit(root)
    committed_by_agent[agent_id] = {"sha": sha, "files": list(files)}
    bucket: list[str] = session_state.setdefault("changed_files", [])
    for f in files:
        if f and f not in bucket:
            bucket.append(f)


def _format_patched_block(committed_by_agent: dict[str, dict[str, Any]]) -> str:
    if not committed_by_agent:
        return "## Patched files this iteration\n(no agent writes this iteration)"
    lines = ["## Patched files this iteration"]
    for agent_id, info in committed_by_agent.items():
        for path in info.get("files", []):
            lines.append(f"- {path} (by {agent_id})")
    return "\n".join(lines)


def make_audit_iteration_executor(
    repo_root: Path, max_iterations: int, game_knowledge: Optional[KnowledgeProtocol] = None
):
    agents = build_agents(repo_root, game_knowledge=game_knowledge)
    specialist_keys = ("storytelling", "ui_ux", "game_design")
    root = repo_root.resolve()

    def audit_iteration(step_input: StepInput, session_state: dict[str, Any]) -> StepOutput:
        session_state.setdefault("audit_outputs", {})
        session_state.setdefault("changed_files", [])
        session_state.setdefault("audit_branch", None)

        iteration_index = int(session_state.get("audit_loop_index", 0))
        first_pass = iteration_index == 0

        raw_input = step_input.get_input_as_string() or ""
        owners_raw = session_state.get("owners_queue")
        owners_set: set[str] = set(owners_raw) if isinstance(owners_raw, list) else set()

        prior = ""
        if hasattr(step_input, "get_all_previous_content"):
            prior = step_input.get_all_previous_content() or ""

        blocks: list[str] = ["## Audit scope (user)\n" + raw_input.strip()]
        if prior:
            blocks.append("## Prior workflow context\n" + prior[:12000])

        base_context = "\n\n".join(blocks)
        out: dict[str, str] = {}
        committed_by_agent: dict[str, dict[str, Any]] = {}

        if first_pass or "auditor" in owners_set:
            msg = base_context + "\n\nRespond with prioritized audit findings for this scope."
            ro = agents["auditor"].run(msg)
            out["auditor"] = _run_output_text(ro)
            session_state["audit_outputs"]["auditor"] = out["auditor"]
            _commit_agent_writes(root, iteration_index, "auditor", session_state, committed_by_agent)
        else:
            out["auditor"] = str(session_state["audit_outputs"].get("auditor", ""))

        specialists_ran = False
        spec_intro = (
            "Auditor output:\n```\n"
            + (out["auditor"] or "")[:20000]
            + "\n```\n\nFocus on your domain only; cite concrete paths under src/."
        )

        for key in specialist_keys:
            if first_pass or key in owners_set:
                ro = agents[key].run(base_context + "\n\n" + spec_intro)
                out[key] = _run_output_text(ro)
                session_state["audit_outputs"][key] = out[key]
                specialists_ran = True
                _commit_agent_writes(root, iteration_index, key, session_state, committed_by_agent)
            else:
                out[key] = str(session_state["audit_outputs"].get(key, ""))

        senior_needed = (
            first_pass
            or "senior_developer" in owners_set
            or specialists_ran
            or "auditor" in owners_set
        )

        if senior_needed:
            senior_msg = "\n\n".join(
                [
                    base_context,
                    "## Auditor\n" + (out["auditor"] or "")[:16000],
                    "## Storytelling\n" + (out["storytelling"] or "")[:12000],
                    "## UI/UX\n" + (out["ui_ux"] or "")[:12000],
                    "## Game design\n" + (out["game_design"] or "")[:12000],
                    "Apply patches directly via apply_patch / write_repo_file when changes are warranted.",
                ]
            )
            ro = agents["senior_developer"].run(senior_msg)
            out["senior_developer"] = _run_output_text(ro)
            session_state["audit_outputs"]["senior_developer"] = out["senior_developer"]
            _commit_agent_writes(root, iteration_index, "senior_developer", session_state, committed_by_agent)
        else:
            out["senior_developer"] = str(session_state["audit_outputs"].get("senior_developer", ""))

        patched_block = _format_patched_block(committed_by_agent)
        verification_block = (
            "## Verification expected\n"
            "If any files were patched this iteration, run `execute_command(\"npm run test\")` "
            "and, if scenes changed, call `run_validate_scenes`. Reject with a `- ❌ [<agent_id>]` "
            "line citing the failing output, tagging the agent that committed the offending file "
            "(see the (by <agent_id>) markers above)."
        )
        reviewer_msg = "\n\n".join(
            [
                base_context,
                "## Auditor\n" + (out["auditor"] or "")[:12000],
                "## Storytelling\n" + (out["storytelling"] or "")[:8000],
                "## UI/UX\n" + (out["ui_ux"] or "")[:8000],
                "## Game design\n" + (out["game_design"] or "")[:8000],
                "## Senior developer\n" + (out["senior_developer"] or "")[:16000],
                patched_block,
                verification_block,
                "Apply the format from your instructions (✅ / ❌ [owner] / STATUS: APPROVED).",
            ]
        )
        rro = agents["reviewer"].run(reviewer_msg)
        out["reviewer"] = _run_output_text(rro)
        session_state["audit_outputs"]["reviewer"] = out["reviewer"]
        _commit_agent_writes(root, iteration_index, "reviewer", session_state, committed_by_agent)

        parsed = parse_reviewer_output(out["reviewer"])
        if parsed.approved:
            session_state["owners_queue"] = []
            stop_loop = True
        else:
            q = list(parsed.owners)
            if not q:
                q = ["senior_developer"]
            session_state["owners_queue"] = q
            stop_loop = False

        next_idx = iteration_index + 1
        session_state["audit_loop_index"] = next_idx

        if next_idx >= max_iterations and not parsed.approved:
            stop_loop = True

        report = "\n\n".join(f"### {k}\n{v}" for k, v in out.items())
        payload = {
            "approved": parsed.approved,
            "stop_loop": stop_loop,
            "owners_next": list(parsed.owners),
            "raw_fail_lines": list(parsed.raw_fail_lines),
            "markdown_report": report,
            "loop_index": next_idx,
            "max_iterations": max_iterations,
            "forced_stop_max_iterations": bool(next_idx >= max_iterations and not parsed.approved),
            "audit_branch": session_state.get("audit_branch"),
            "committed_files": [
                p for info in committed_by_agent.values() for p in info.get("files", [])
            ],
            "committed_by_agent": committed_by_agent,
        }
        return StepOutput(
            step_name="audit_iteration",
            step_type="Step",
            content=json.dumps(payload, ensure_ascii=False),
            success=True,
        )

    return audit_iteration


def end_loop_on_approval(iteration_results: list[Any]) -> bool:
    if not iteration_results:
        return True
    last = iteration_results[-1]
    raw = last.content if isinstance(last.content, str) else str(last.content or "")
    try:
        data = json.loads(raw)
        return bool(data.get("stop_loop"))
    except json.JSONDecodeError:
        return True


def build_audit_workflow(
    repo_root_arg: Path | None = None,
    max_iterations: int | None = None,
    db: Any | None = None,
    game_knowledge: Optional[KnowledgeProtocol] = None,
) -> Workflow:
    root = (repo_root_arg or repo_root()).resolve()
    cap = max_iterations if max_iterations is not None else audit_flow_max_iterations()
    executor = make_audit_iteration_executor(root, cap, game_knowledge=game_knowledge)
    wf_db = make_agent_db() if db is None else db
    wf_kw: dict[str, Any] = {}
    if wf_db is not None:
        wf_kw["db"] = wf_db
        wf_kw["add_workflow_history_to_steps"] = True
        wf_kw["num_history_runs"] = 3
    return Workflow(
        id="audit-flow",
        name="AuditFlow",
        description="Auditor → specialists → senior developer → reviewer, with rework loop",
        **wf_kw,
        steps=[
            Loop(
                name="audit_rework_loop",
                max_iterations=cap,
                end_condition=end_loop_on_approval,
                steps=[
                    Step(
                        name="audit_iteration",
                        executor=executor,
                        description="One audit cycle; JSON metadata for loop control",
                    ),
                ],
            ),
        ],
    )


def run_audit_flow(
    user_prompt: str,
    *,
    repo_root_arg: Path | None = None,
    max_iterations: int | None = None,
    session_state: dict[str, Any] | None = None,
    game_knowledge: Optional[KnowledgeProtocol] = None,
) -> Any:
    """Run AuditFlow synchronously; returns ``WorkflowRunOutput``.

    Creates a throwaway ``agno/audit-flow/<UTC-timestamp>`` branch (unless the
    caller pre-populated ``session_state["audit_branch"]``) so every agent
    commit lands in isolation off the current HEAD. Callers should usually
    run :func:`game_dev_crew.workflow.git_isolation.ensure_clean_tree` first
    (the CLI does this in ``cmd_audit_flow``).
    """
    maybe_setup_tracing(make_agent_db())
    root = (repo_root_arg or repo_root()).resolve()
    state = session_state if session_state is not None else {}
    if not state.get("audit_branch"):
        state["audit_branch"] = create_audit_branch(root)
    wf = build_audit_workflow(
        repo_root_arg=root,
        max_iterations=max_iterations,
        game_knowledge=game_knowledge,
    )
    return wf.run(input=user_prompt, session_state=state, add_session_state_to_context=True)
