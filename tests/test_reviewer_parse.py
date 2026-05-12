"""Tests for reviewer output parsing."""

from __future__ import annotations

import pytest

from game_dev_crew.workflow.reviewer_parse import parse_reviewer_output


@pytest.mark.parametrize(
    ("text", "approved", "owners", "raw_len"),
    [
        ("", True, (), 0),
        ("   \n", True, (), 0),
        ("STATUS: APPROVED\n", True, (), 0),
        ("status: approved\n", True, (), 0),
        (
            "Some text\n- ❌ [storytelling] fix pacing\n",
            False,
            ("storytelling",),
            1,
        ),
        (
            "- ❌ [unknown] x\n- ❌ [ui_ux] y\n",
            False,
            ("ui_ux",),
            2,
        ),
        (
            "- ❌ [game_design] a\n- ❌ [auditor] b\n",
            False,
            ("auditor", "game_design"),
            2,
        ),
        (
            "- ❌ [senior_developer] z\n- ❌ [storytelling] s\n",
            False,
            ("storytelling", "senior_developer"),
            2,
        ),
        (
            "❌ but no bracket owner line",
            False,
            (),
            0,
        ),
        (
            "All good no failures",
            True,
            (),
            0,
        ),
    ],
)
def test_parse_reviewer_output(
    text: str,
    approved: bool,
    owners: tuple[str, ...],
    raw_len: int,
) -> None:
    r = parse_reviewer_output(text)
    assert r.approved is approved
    assert r.owners == owners
    assert len(r.raw_fail_lines) == raw_len


def test_owner_ordering_when_multiple_valid() -> None:
    text = (
        "- ❌ [senior_developer] last in file\n"
        "- ❌ [auditor] first in owner order\n"
        "- ❌ [ui_ux] middle\n"
    )
    r = parse_reviewer_output(text)
    assert r.approved is False
    assert r.owners == ("auditor", "ui_ux", "senior_developer")
