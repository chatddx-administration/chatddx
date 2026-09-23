import pytest

from chatddx.eval.scorers import (
    UnreadableOutputError,
    exact_match,
    pattern_matches,
    reciprocal_rank,
    resolve_scorer,
    scorer_reads,
)

DIAGNOSES = {
    "title": "diagnoses",
    "type": "array",
    "items": {"type": "string", "description": "The name of a diagnosis."},
}


@pytest.mark.parametrize(
    "pattern, text, expected",
    [
        # A bare word is a case-insensitive substring.
        ("pneumonia", "likely community-acquired pneumonia", True),
        ("pneumonia", "PNEUMONIA, bilateral", True),
        ("pneumonia", "no findings of note", False),
        # `&` needs every term, anywhere in the text.
        ("acute & kidney & injury", "acute injury of the kidney", True),
        ("acute & kidney & injury", "acute kidney disease", False),
        # `|` needs one.
        ("cirrosis | cirrhosis", "signs of cirrhosis", True),
        ("cirrosis | cirrhosis", "a healthy liver", False),
        # `&` binds tighter than `|`, so this is `copd | (exacerbation & pulmonary)`.
        ("copd | exacerbation & pulmonary", "copd", True),
        ("copd | exacerbation & pulmonary", "pulmonary exacerbation", True),
        ("copd | exacerbation & pulmonary", "an exacerbation", False),
        # Parentheses override that.
        ("(copd | exacerbation) & pulmonary", "copd", False),
        ("(copd | exacerbation) & pulmonary", "pulmonary copd", True),
        # Several words in a row are one phrase, not several terms.
        ("aortic stenosis", "aortic stenosis", True),
        ("aortic stenosis", "stenosis, aortic", False),
    ],
)
def test_pattern_matches(pattern: str, text: str, expected: bool):
    assert pattern_matches(pattern, text) is expected


@pytest.mark.parametrize("pattern", ["(pneumonia", "", "pneumonia &"])
def test_a_malformed_pattern_is_rejected_rather_than_silently_missed(pattern: str):
    with pytest.raises(ValueError):
        _ = pattern_matches(pattern, "pneumonia")


def test_a_pattern_of_several_lines_is_rejected_rather_than_read_as_one_phrase():
    # the shape an expectation had while it ranked its own answers, which
    # would otherwise read as the phrase "pneumonia copd"
    with pytest.raises(ValueError, match="single line"):
        _ = reciprocal_rank(["pneumonia"], "pneumonia\ncopd")


@pytest.mark.parametrize(
    "output, score, rank",
    [
        (["community-acquired pneumonia", "copd"], 100, 1),
        (["asthma", "copd exacerbation"], 50, 2),
        (["asthma", "bronchitis", "heart failure", "Pneumonia"], 25, 4),
        (["asthma", "bronchitis"], 0, None),
        ([], 0, None),
    ],
)
def test_reciprocal_rank_is_decided_by_the_first_item_that_matches(
    output: list[str],
    score: float,
    rank: int | None,
):
    result = reciprocal_rank(output, "pneumonia | copd")

    assert result["score"] == score
    assert result["rank"] == rank
    assert result["matched"] == (output[rank - 1] if rank else None)
    assert result["expected"] == "pneumonia | copd"


def test_a_pattern_is_matched_against_one_item_at_a_time():
    # the terms are in the list, but no single diagnosis carries both
    result = reciprocal_rank(["acute kidney", "injury"], "kidney & injury")

    assert result["score"] == 0


def test_exact_match_compares_text():
    assert exact_match("yes", "yes")["correct"] is True
    assert exact_match("yes.", "yes")["correct"] is False


def test_scorers_resolve_by_the_command_their_trail_carries():
    assert resolve_scorer("reciprocal_rank").judge is reciprocal_rank
    assert resolve_scorer("exact_match").judge is exact_match


def test_an_unknown_command_names_what_it_could_have_been():
    with pytest.raises(LookupError, match="exact_match, reciprocal_rank"):
        _ = resolve_scorer("regex_match")


def test_reciprocal_rank_reads_a_list_and_nothing_else():
    scorer = resolve_scorer("reciprocal_rank")

    assert scorer.reads(DIAGNOSES)
    # free text: the empty definition
    assert not scorer.reads({})
    # the same list, wrapped in an object
    assert not scorer.reads(
        {"type": "object", "properties": {"diagnoses": DIAGNOSES}},
    )
    # a list, but of anything
    assert not scorer.reads({"type": "array"})


def test_exact_match_reads_free_text():
    scorer = resolve_scorer("exact_match")

    assert scorer.reads({})
    assert not scorer.reads(DIAGNOSES)


def test_a_scorer_this_code_does_not_have_reads_nothing_it_can_vouch_for():
    assert scorer_reads("no_such_scorer", DIAGNOSES) is None
    assert scorer_reads("reciprocal_rank", DIAGNOSES) is True
    assert scorer_reads("reciprocal_rank", {}) is False


def test_an_output_is_checked_against_what_its_scorer_accepts():
    scorer = resolve_scorer("reciprocal_rank")

    scorer.check(["pneumonia"])

    with pytest.raises(UnreadableOutputError, match="reciprocal_rank"):
        scorer.check("pneumonia")

    with pytest.raises(UnreadableOutputError):
        scorer.check(["pneumonia", {"diagnosis": "copd"}])
