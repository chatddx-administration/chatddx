"""How two scorers read the same samples."""

from pathlib import Path

from inspect_ai.log import (
    EvalConfig,
    EvalDataset,
    EvalLog,
    EvalSample,
    EvalSpec,
    write_eval_log,
)
from inspect_ai.scorer import Score
from typer.testing import CliRunner

from chatddx.logs.agreement import Disagreement, agreement

NAN = float("nan")


def log_of(*pairs: tuple[float, float]) -> EvalLog:
    """A log whose samples `pattern` and `judge` scored, a pair each."""
    return EvalLog(
        eval=EvalSpec(
            created="2026-09-25T00:00:00+00:00",
            task="cell",
            dataset=EvalDataset(),
            model="none/none",
            config=EvalConfig(),
        ),
        samples=[
            EvalSample(
                id=f"case-{i}",
                epoch=1,
                input="a vignette",
                target="",
                scores={
                    "pattern": Score(value=pattern, answer=f"p{i}"),
                    "judge": Score(value=judge, answer=f"j{i}"),
                },
            )
            for i, (pattern, judge) in enumerate(pairs, 1)
        ],
    )


def test_agreement_counts_what_each_found_and_lists_where_they_differ():
    measured = agreement(
        [log_of((0.5, 0.5), (0.0, 0.0), (1.0, 0.0), (0.0, 0.5), (1.0, 0.5))],
        "pattern",
        "judge",
    )

    assert (
        measured.both,
        measured.neither,
        measured.first_only,
        measured.second_only,
        measured.same,
    ) == (2, 1, 1, 1, 2)
    assert measured.disagreements == (
        Disagreement("cell", "case-3", 1, (1.0, 0.0), ("p3", "j3")),
        Disagreement("cell", "case-4", 1, (0.0, 0.5), ("p4", "j4")),
        Disagreement("cell", "case-5", 1, (1.0, 0.5), ("p5", "j5")),
    )


def test_kappa_discounts_what_chance_would_agree_on():
    assert agreement([log_of((1, 1), (0, 0))], "pattern", "judge").kappa == 1.0
    assert agreement([log_of((1, 0), (0, 1))], "pattern", "judge").kappa == -1.0
    assert (
        agreement([log_of((1, 1), (0, 0), (1, 0), (0, 1))], "pattern", "judge").kappa
        == 0.0
    )


def test_a_sample_either_left_unscored_is_left_out():
    measured = agreement([log_of((NAN, 1.0), (1.0, NAN))], "pattern", "judge")

    assert measured.samples == 0
    assert measured.kappa is None
    assert agreement([log_of((1, 1))], "pattern", "neither").samples == 0


def test_the_command_says_how_two_scorers_read_the_logs_and_where_they_differ(
    tmp_path: Path,
):
    from chatddx.manage import app

    _ = write_eval_log(log_of((1.0, 1.0), (0.0, 0.5)), str(tmp_path / "a.eval"))
    _ = write_eval_log(log_of((0.0, 0.0)), str(tmp_path / "b.eval"))

    said = CliRunner().invoke(app, ["agreement", "pattern", "judge", str(tmp_path)])

    assert said.exit_code == 0, said.output
    words = " ".join(said.output.split())
    assert "pattern and judge, over 3 samples" in words
    assert "kappa on found 0.40" in words
    assert "where they differ: task sample epoch pattern judge" in words
    assert "cell case-2 1 0 p2 0.5 j2" in words

    said = CliRunner().invoke(app, ["agreement", "pattern", "none", str(tmp_path)])

    assert said.exit_code == 1
    assert "no sample was scored by both pattern and none" in said.output
