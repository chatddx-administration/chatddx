from collections.abc import Callable

import pytest

type Say = Callable[..., str]

pytestmark = pytest.mark.django_db


def test_stacks_are_listed_with_whose_they_are(say: Say):
    written = say("stacks")

    for stack in (
        "qwen3-8b-awq@pelle",
        "gpt-oss-20b@malborg",
        "qwen3-8b-awq@malborg",
        "qwen3-8b-awq@fake",
        "gpt-oss-20b@fake",
    ):
        assert stack in written

    assert "http://localhost:12099/v1/" in written
    assert "archive" in written


def test_configurations_are_listed_with_their_variations(say: Say):
    row = next(
        line for line in say("configurations").splitlines() if "free-text" in line
    )

    assert row.split() == [
        "free-text",
        "ddx",
        "free-text",
        "auto",
        "default",
        "recommended",
        "—",
        "archive",
    ]


def test_cases_are_listed_by_name(say: Say):
    written = say("cases")

    assert "case-1  case-2" in written
    assert "2 cases" in written
