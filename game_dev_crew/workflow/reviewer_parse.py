"""Parse Reviewer output for rework routing (❌ lines and STATUS)."""

from __future__ import annotations

import re
from dataclasses import dataclass

FAIL_LINE = re.compile(
    r"^\s*-\s*❌\s*\[([a-zA-Z0-9_]+)\]\s*(.*)$",
    re.MULTILINE,
)

APPROVED_MARK = re.compile(r"^\s*STATUS:\s*APPROVED\s*$", re.MULTILINE | re.IGNORECASE)

VALID_OWNERS = frozenset(
    {
        "auditor",
        "storytelling",
        "ui_ux",
        "game_design",
        "senior_developer",
    }
)

OWNER_ORDER = ("auditor", "storytelling", "ui_ux", "game_design", "senior_developer")


@dataclass(frozen=True)
class ReviewParseResult:
    approved: bool
    """True if no ❌ lines and (optional) explicit APPROVED, or only ✅."""

    owners: tuple[str, ...]
    """Ordered unique owners to re-run, subset of OWNER_ORDER."""

    raw_fail_lines: tuple[str, ...]


def parse_reviewer_output(text: str) -> ReviewParseResult:
    if not text or not text.strip():
        return ReviewParseResult(approved=True, owners=(), raw_fail_lines=())

    if APPROVED_MARK.search(text):
        return ReviewParseResult(approved=True, owners=(), raw_fail_lines=())

    owners: list[str] = []
    raw_lines: list[str] = []
    seen: set[str] = set()

    for m in FAIL_LINE.finditer(text):
        owner = m.group(1).strip().lower()
        raw_lines.append(m.group(0).strip())
        if owner not in VALID_OWNERS:
            continue
        if owner not in seen:
            seen.add(owner)
            owners.append(owner)

    ordered = tuple(o for o in OWNER_ORDER if o in owners)

    if not ordered:
        if "❌" in text:
            return ReviewParseResult(approved=False, owners=(), raw_fail_lines=tuple(raw_lines))
        return ReviewParseResult(approved=True, owners=(), raw_fail_lines=())

    return ReviewParseResult(approved=False, owners=ordered, raw_fail_lines=tuple(raw_lines))
