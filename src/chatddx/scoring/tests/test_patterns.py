"""
The pattern language, held to what an answer says, and the scorers that
hold answers to it.
"""

import inspect

import pytest

from chatddx.core import settings
from chatddx.repo.parsers.inventory import parse
from chatddx.runtime.implementation import SCORERS, implementation
from chatddx.scoring.scorers.patterns import (
    Pattern,
    Scored,
    first_mention,
    mentions,
    reciprocal_rank,
)


@pytest.mark.parametrize(
    "pattern, text, at",
    [
        ("pneumonia", "Likely pneumonia", 7),
        ("PNEUMONIA", "pneumonia", 0),
        ("mi", "Iron deficiency anemia", None),
        ("mi", "Acute MI", 6),
        ("hus", "Thus far unexplained fever", None),
        ("stone", "Kidney stones", None),
        ("stone*", "Kidney stones", 7),
        ("meningit*", "Viral meningitis", 6),
        ("tumör", "Hjärntumör", None),
        ("hjärntumör", "Misstänkt hjärntumör", 10),
        ("acute coronary syndrome", "Acute coronary syndrome (ACS)", 0),
        ("coronary acute", "Acute coronary syndrome", None),
        ("parkinson's disease", "Parkinson's disease", 0),
        ("gastro & intestinal", "Gastro-intestinal bleed", 0),
        ("gastro & intestinal", "Gastrointestinal bleed", None),
        ("copd | exacerbation & pulmonary", "Pulmonary exacerbation", 0),
        ("copd | exacerbation & pulmonary", "An exacerbation", None),
        ("copd | exacerbation & pulmonary", "Known COPD", 6),
        ("(renal | kidney) & (colic | stone*)", "Renal colic", 0),
        ("(renal | kidney) & (colic | stone*)", "Kidney stones", 0),
        ("(renal | kidney) & (colic | stone*)", "Renal failure", None),
        ("liver & failure", "Failure of the liver", 0),
    ],
)
def test_a_pattern_finds_whole_words(pattern: str, text: str, at: int | None):
    assert Pattern(pattern).find(text) == at


@pytest.mark.parametrize(
    "pattern, problem",
    [
        ("", "at least one word"),
        ("(pneumonia | copd", "never closed"),
        ("pneumonia &", "a word is missing"),
        ("pneumonia ) copd", r"unexpected '\)'"),
        ("* | copd", "names no word"),
    ],
)
def test_a_pattern_that_doesn_t_read_is_refused(pattern: str, problem: str):
    with pytest.raises(ValueError, match=problem):
        _ = Pattern(pattern)


INVENTORIES = ["inventory.toml", "test-inventory.toml"]


@pytest.mark.parametrize("path", INVENTORIES, ids=lambda path: path)
def test_every_target_reads(path: str):
    """What the pattern scorers read of a case's targets: each a pattern."""
    for _, details in parse(settings.INVENTORY_PATH / path).case.values():
        for target in details.targets.values():
            if target is not False:
                _ = Pattern(target)


@pytest.mark.parametrize("path", INVENTORIES, ids=lambda path: path)
def test_every_scorer_runs_a_function_that_takes_its_arguments(path: str):
    """
    A scorer's function takes the view's items and the target, and the
    scorer's arguments beside them, as a tool's takes its parameters.
    """
    for name, (scorer, _) in parse(settings.INVENTORY_PATH / path).scorer.items():
        function = implementation(scorer.function, SCORERS).function

        try:
            _ = inspect.signature(function).bind([], "target", **scorer.args)
        except TypeError as e:
            pytest.fail(f"{name}: {e}")


def test_the_reciprocal_rank_is_that_of_the_first_diagnosis_found():
    differential = ["Pulmonary embolism", "Pneumonia", "Pneumonia, atypical"]

    assert reciprocal_rank(differential, "pneumonia") == Scored(0.5, "2. Pneumonia")
    assert reciprocal_rank(differential, "sepsis") == Scored(0.0, reason="not listed")
    assert reciprocal_rank(None, "pneumonia") == Scored(0.0, reason="no answer")


@pytest.mark.parametrize(
    "target, differential",
    [
        (
            "myocardial & infarction | mi | acs | acute & coronary & syndrome",
            ["Iron deficiency anemia"],
        ),
        ("uti | urinary & infection* | cystitis | urosepsis", ["Acute cholecystitis"]),
        ("hemolytic & uremic & syndrome | hus", ["Thus far unexplained fever"]),
        ("liver & failure | cirrosis | cirrhosis", ["Heart failure", "Liver abscess"]),
        ("overdose | drug & use | intoxication", ["Pain because of a fall"]),
        ("(gastro & intestinal | gi) & inflammation", ["Allergic inflammation"]),
    ],
)
def test_what_the_old_scorer_found_in_parts_of_words_is_not_found(
    target: str, differential: list[str]
):
    assert reciprocal_rank(differential, target).value == 0


def test_the_first_mention_is_counted_in_characters_to_its_first_word():
    text = "Cough and fever. Pneumonia is likely.\nPE is less likely."

    assert first_mention([text], "pneumonia") == Scored(17.0, "Pneumonia is likely.")
    assert first_mention([text], "pe | embolism") == Scored(38.0, "PE is less likely.")
    assert first_mention([text], "sepsis") == Scored(None, reason="never named")
    assert first_mention(None, "sepsis") == Scored(None, reason="no answer")


def test_a_first_mention_holds_the_target_to_one_sentence_at_a_time():
    text = "Heart failure is likely. A liver abscess is not."

    assert first_mention([text], "liver & failure").value is None
    assert first_mention([text], "liver & abscess").value == 27


def test_mentions_says_whether_the_target_is_named_at_all():
    assert mentions(["Admit to the surgical ward."], "admit*") == Scored(
        1.0, "Admit to the surgical ward."
    )
    assert mentions(["Discharge home."], "admit*") == Scored(0.0, reason="not named")
    assert mentions([], "admit*") == Scored(0.0, reason="not named")
    assert mentions(None, "admit*") == Scored(0.0, reason="no answer")


def test_mentions_with_no_target_expects_nothing_named():
    assert mentions([], None) == Scored(1.0, reason="none named, as expected")
    assert mentions(["Signs of sepsis."], None) == Scored(
        0.0, "Signs of sepsis.", "none expected"
    )
    assert mentions(None, None) == Scored(0.0, reason="no answer")
