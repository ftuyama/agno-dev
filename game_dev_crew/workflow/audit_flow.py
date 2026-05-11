"""AuditFlow: Agno Workflow + Loop with reviewer-driven rework."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from agno.workflow import Workflow
from agno.workflow.loop import Loop
from agno.workflow.step import Step
from agno.workflow.types import StepInput, StepOutput

from game_dev_crew.config import audit_flow_max_iterations, repo_root
from game_dev_crew.crew.agents import build_agents
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


def make_audit_iteration_executor(repo_root: Path, max_iterations: int):
    agents = build_agents(repo_root)
    specialist_keys = ("storytelling", "ui_ux", "game_design")

    def audit_iteration(step_input: StepInput, session_state: dict[str, Any]) -> StepOutput:
        session_state.setdefault("audit_outputs", {})

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

        if first_pass or "auditor" in owners_set:
            msg = base_context + "\n\nRespond with prioritized audit findings for this scope."
            ro = agents["auditor"].run(msg)
            out["auditor"] = _run_output_text(ro)
            session_state["audit_outputs"]["auditor"] = out["auditor"]
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
                    "Produce implementation plan and textual patches only.",
                ]
            )
            ro = agents["senior_developer"].run(senior_msg)
            out["senior_developer"] = _run_output_text(ro)
            session_state["audit_outputs"]["senior_developer"] = out["senior_developer"]
        else:
            out["senior_developer"] = str(session_state["audit_outputs"].get("senior_developer", ""))

        reviewer_msg = "\n\n".join(
            [
                base_context,
                "## Auditor\n" + (out["auditor"] or "")[:12000],
                "## Storytelling\n" + (out["storytelling"] or "")[:8000],
                "## UI/UX\n" + (out["ui_ux"] or "")[:8000],
                "## Game design\n" + (out["game_design"] or "")[:8000],
                "## Senior developer\n" + (out["senior_developer"] or "")[:16000],
                "Apply the format from your instructions (✅ / ❌ [owner] / STATUS: APPROVED).",
            ]
        )
        rro = agents["reviewer"].run(reviewer_msg)
        out["reviewer"] = _run_output_text(rro)
        session_state["audit_outputs"]["reviewer"] = out["reviewer"]

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
) -> Workflow:
    root = (repo_root_arg or repo_root()).resolve()
    cap = max_iterations if max_iterations is not None else audit_flow_max_iterations()
    executor = make_audit_iteration_executor(root, cap)
    return Workflow(
        name="AuditFlow",
        description="Auditor → specialists → senior developer → reviewer, with rework loop",
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
) -> Any:
    """Run AuditFlow synchronously; returns ``WorkflowRunOutput``."""
    wf = build_audit_workflow(repo_root_arg=repo_root_arg, max_iterations=max_iterations)
    state = session_state if session_state is not None else {}
    return wf.run(input=user_prompt, session_state=state, add_session_state_to_context=True)
