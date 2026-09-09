"""Pure tests for the `regex_match` pattern grammar (`row_matches`) -- no DB
needed, these just exercise the parser/matcher directly."""

import pytest

from chatddx.experiment.scorers import row_matches


@pytest.mark.parametrize(
    ("row", "text", "expected"),
    [
        # Bare word: plain case-insensitive substring match.
        ("pneumonia", "the patient has pneumonia", True),
        ("pneumonia", "PNEUMONIA is suspected", True),
        ("pneumonia", "no lung findings", False),
        # Space between words is literal: a run of bare words is one
        # phrase that must appear together, separated by exactly one
        # space -- not each word independently.
        ("a b | c", "it says a b somewhere", True),
        ("a b | c", "it says c somewhere", True),
        ("a b | c", "it only says a here", False),
        ("a b | c", "it only says b here", False),
        ("a b | c", "a  b are far apart", False),
        ("a b | c", "b a swapped around", False),
        # `|` is OR.
        ("uti | cystitis", "diagnosed with uti", True),
        ("uti | cystitis", "diagnosed with cystitis", True),
        ("uti | cystitis", "diagnosed with pyelonephritis", False),
        # `&` is AND: both sides must appear, anywhere in the text.
        ("gastro & intestinal", "gastro problem, intestinal too", True),
        ("gastro & intestinal", "intestinal issue, gastro too", True),
        ("gastro & intestinal", "just gastro here", False),
        ("gastro & intestinal", "just intestinal here", False),
        # `&` binds tighter than `|`.
        (
            "physiological & jaundice | neonatal & jaundice",
            "physiological jaundice noted",
            True,
        ),
        (
            "physiological & jaundice | neonatal & jaundice",
            "neonatal jaundice noted",
            True,
        ),
        (
            "physiological & jaundice | neonatal & jaundice",
            "physiological findings alone",
            False,
        ),
        # Parentheses override precedence.
        ("(diverticular | gi) & bleed", "gi bleed suspected", True),
        ("(diverticular | gi) & bleed", "diverticular bleed suspected", True),
        ("(diverticular | gi) & bleed", "just gi symptoms here", False),
        (
            "copd | ((exacerbation | obstructive) & pulmonary)",
            "acute exacerbation of pulmonary disease",
            True,
        ),
        (
            "copd | ((exacerbation | obstructive) & pulmonary)",
            "obstructive pulmonary disease",
            True,
        ),
        (
            "copd | ((exacerbation | obstructive) & pulmonary)",
            "copd diagnosed",
            True,
        ),
        (
            "copd | ((exacerbation | obstructive) & pulmonary)",
            "acute exacerbation of symptoms",
            False,
        ),
    ],
)
def test_row_matches(row: str, text: str, expected: bool):
    assert row_matches(row, text) is expected


def test_row_matches_rejects_malformed_pattern():
    with pytest.raises(ValueError):
        row_matches("a & | b", "anything")


def test_row_matches_rejects_unbalanced_parens():
    with pytest.raises(ValueError):
        row_matches("(a | b", "anything")
