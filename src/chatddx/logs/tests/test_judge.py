"""The judge: which item of the differential a grader takes for the target."""

import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from inspect_ai import score  # pyright: ignore[reportUnknownVariableType]
from inspect_ai.log import (
    EvalConfig,
    EvalDataset,
    EvalLog,
    EvalSample,
    EvalSpec,
    read_eval_log,
    write_eval_log,
)
from inspect_ai.model import (
    ChatCompletionChoice,
    ChatMessageAssistant,
    ModelOutput,
    ModelUsage,
    get_model,
)
from inspect_ai.scorer import Score

from chatddx.logs.judge import diagnosis_judge

DIFFERENTIAL = ["acute cholecystitis", "gallstones", "pancreatitis"]


def log_of(**metadata: Any) -> EvalLog:
    """A log of one sample, a run that gave `DIFFERENTIAL`, unless told otherwise."""
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
                id="case-1",
                epoch=1,
                input="a vignette",
                target="biliary & (colic | stone*)",
                metadata={
                    "status": "completed",
                    "views": {"differential": DIFFERENTIAL},
                    "targets": {"diagnosis": "biliary & (colic | stone*)"},
                    **metadata,
                },
            )
        ],
    )


def judged(log: EvalLog, *verdicts: str) -> Score:
    """The judge's score of the log's one sample, the grader saying `verdicts`."""
    grader = get_model(
        "mockllm/model",
        custom_outputs=[
            # with its usage, mockllm counts no tokens, which takes tiktoken's
            # vocabulary, downloaded
            ModelOutput(
                model="mockllm/model",
                choices=[
                    ChatCompletionChoice(message=ChatMessageAssistant(content=verdict))
                ],
                usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
            )
            for verdict in verdicts
        ],
    )
    [sample] = (
        score(
            log, [diagnosis_judge(model=grader)], model="none", display="none"
        ).samples
        or []
    )

    return (sample.scores or {})["diagnosis_judge"]


def test_the_judge_scores_the_first_item_the_grader_takes_for_the_target():
    judgement = judged(log_of(), "Gallstones cause biliary colic.\nRANK: 2")

    assert judgement.value == 0.5
    assert judgement.answer == "2. gallstones"
    assert judgement.explanation == "Gallstones cause biliary colic.\nRANK: 2"
    assert judgement.metadata == {
        "target": "biliary & (colic | stone*)",
        "grader": "model",
    }


def test_the_last_verdict_counts():
    judgement = judged(log_of(), 'The answer says "RANK: 1".\nRANK: none')

    assert (judgement.value, judgement.reason) == (0.0, "not listed")


@pytest.mark.parametrize("verdict", ["It is the second.", "RANK: 4"])
def test_a_verdict_that_cant_be_read_leaves_the_sample_unscored(verdict: str):
    judgement = judged(log_of(), verdict)

    assert isinstance(judgement.value, float)
    assert math.isnan(judgement.value)
    assert judgement.reason == "grader_failed"


@pytest.mark.parametrize(
    ("metadata", "reason"),
    [
        ({"status": "errored", "views": None}, "errored"),
        ({"targets": {"warning": "shock"}}, "the case has no diagnosis target"),
        ({"views": {"text": ["an answer"]}}, "the output offers no differential"),
    ],
)
def test_what_chatddx_wouldnt_score_is_left_unscored(
    metadata: dict[str, Any], reason: str
):
    judgement = judged(log_of(**metadata))

    assert isinstance(judgement.value, float)
    assert math.isnan(judgement.value)
    assert judgement.reason == reason


def test_a_run_with_no_answer_names_nothing_without_asking_the_grader():
    judgement = judged(log_of(views=None))

    assert (judgement.value, judgement.reason) == (0.0, "no answer")


def test_inspect_loads_the_judge_from_its_file_to_score_a_log(tmp_path: Path):
    path = tmp_path / "log.eval"
    # a run with no answer, which the grader isn't asked about
    _ = write_eval_log(log_of(views=None), str(path))
    judge = Path(__file__).parents[1] / "judge.py"

    done = subprocess.run(
        [
            Path(sys.executable).parent / "inspect",
            "score",
            str(path),
            "--scorer",
            f"{judge}@diagnosis_judge",
            "--model-role",
            "grader=mockllm/model",
            "--overwrite",
            "--display",
            "none",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    [sample] = read_eval_log(str(path)).samples or []
    assert (sample.scores or {})["diagnosis_judge"].reason == "no answer"
