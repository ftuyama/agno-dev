"""Collect workflow callables for Agno ``Registry`` (DB workflow rehydration)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


def collect_workflow_functions_for_registry(workflows: Sequence[Any]) -> list[Callable[..., Any]]:
    """Gather ``executor`` and ``Loop.end_condition`` callables from in-memory workflows.

    Serialized workflow configs in SQLite store ``executor_ref`` and named loop end
    conditions; :func:`agno.workflow.workflow.get_workflows` resolves them via
    ``registry.get_function(__name__)``. AgentOS must register these callables on the
    same ``Registry`` instance passed to the OS.
    """
    funcs: list[Callable[..., Any]] = []
    seen: set[str] = set()

    def add_fn(fn: Any) -> None:
        if fn is None or not callable(fn):
            return
        name = getattr(fn, "__name__", None)
        if not isinstance(name, str) or not name or name in seen:
            return
        seen.add(name)
        funcs.append(fn)

    def walk(node: Any) -> None:
        if node is None:
            return
        ec = getattr(node, "end_condition", None)
        if ec is not None and callable(ec):
            add_fn(ec)
        ex = getattr(node, "executor", None)
        if ex is not None and callable(ex):
            add_fn(ex)
        for child in getattr(node, "steps", None) or ():
            walk(child)

    for wf in workflows:
        for top in getattr(wf, "steps", None) or ():
            walk(top)
    return funcs
