import pytest

from chatddx.eval.scorers import (
    exact_match,
    regex_match,
    resolve_scorer,
    row_matches,
)


@pytest.mark.parametrize(
    "row, text, expected",
    [
        # A bare row is a case-insensitive substring.
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
def test_row_matches(row: str, text: str, expected: bool):
    assert row_matches(row, text) is expected


@pytest.mark.parametrize("row", ["(pneumonia", "", "pneumonia &"])
def test_a_malformed_row_is_rejected_rather_than_silently_missed(row: str):
    with pytest.raises(ValueError):
        _ = row_matches(row, "pneumonia")


def test_scorers_resolve_by_the_command_their_trail_carries():
    assert resolve_scorer("regex_match") is regex_match
    assert resolve_scorer("exact_match") is exact_match


def test_an_unknown_command_names_what_it_could_have_been():
    with pytest.raises(LookupError, match="exact_match, regex_match"):
        _ = resolve_scorer("no_such_scorer")
