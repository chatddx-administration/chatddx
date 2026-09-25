"""
A cell's runs as an inspect log: a sample per draw of a case, and in its
metadata what inspect has no place for.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from inspect_ai.analysis import samples_df
from inspect_ai.event import ModelEvent
from inspect_ai.log import EvalLog, EvalSample, read_eval_log
from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, ContentReasoning

from chatddx.history.models import RunModel, RunStatus
from chatddx.logs.export import cell_log, write
from chatddx.logs.tests.conftest import Run

pytestmark = pytest.mark.django_db


def log_of(identity: str = "alex") -> EvalLog:
    """The log of the cell `identity` ran last."""
    latest = RunModel.objects.filter(owner__name=identity).latest("pk")

    return cell_log(identity, latest.trial.configuration, latest.trial.stack, "cell")


def model_events(sample: EvalSample) -> list[ModelEvent]:
    return [event for event in sample.events if isinstance(event, ModelEvent)]


def failing(_request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(400, json={"error": {"message": "no such model"}})


def test_a_seeded_trial_is_a_draw_whose_epoch_is_its_seeds_place(run: Run):
    run(
        "cell plan qwen3-8b-awq@fake",
        "run case-1 7",
        "run case-1 7",
        "run case-2 3",
        "run case-1",
        "run case-1",
    )

    samples = log_of().samples or []

    assert [(s.id, s.epoch, s.metadata["seed"]) for s in samples] == [
        ("case-1", 2, 7),
        ("case-1", 3, None),
        ("case-1", 4, None),
        ("case-2", 1, 3),
    ]
    assert samples[0].metadata["run"] == str(
        RunModel.objects.filter(trial__seed=7).latest("pk").uuid
    )


def test_a_seeded_trial_is_drawn_by_its_latest_run_that_completed(
    run_as: Callable[..., Run],
):
    run_as("alex")("cell plan qwen3-8b-awq@fake", "run case-1 7")
    run_as("alex", httpx2.MockTransport(failing))(
        "cell plan qwen3-8b-awq@fake", "run case-1 7"
    )

    [sample] = log_of().samples or []

    assert sample.metadata["run"] == str(
        RunModel.objects.get(status=RunStatus.COMPLETED).uuid
    )
    assert sample.error is None


def test_a_sample_holds_what_the_llm_was_sent_and_what_came_of_it(run: Run):
    run("cell plan qwen3-8b-awq@fake", "run case-1")
    recorded = RunModel.objects.get()

    log = log_of()
    [sample] = log.samples or []

    assert log.eval.model == "vllm/qwen3-8b-awq@fake"
    assert isinstance(sample.input, list)
    assert [(message.role, message.text) for message in sample.input][1] == (
        "user",
        "case vignette 1",
    )
    assert sample.input[0].role == "system"
    assert sample.target == "fake & diagnosis & (b | 2)"
    assert json.loads(sample.output.completion) == recorded.answer
    assert sample.output.stop_reason == "stop"
    assert isinstance(sample.messages[-1].content, list)
    assert isinstance(sample.messages[-1].content[0], ContentReasoning)
    assert sample.metadata["output"] == "management-plan"
    assert sample.metadata["stack"] == "qwen3-8b-awq@fake"
    assert sample.metadata["views"]["differential"] == [
        "fake diagnosis 1",
        "fake diagnosis 2",
        "fake diagnosis 3",
    ]
    assert sample.metadata["targets"] == {
        "diagnosis": "fake & diagnosis & (b | 2)",
        "warning": "acute & warning",
        "disposition": "admit*",
    }

    [event] = model_events(sample)
    assert event.call is not None
    response: Any = event.call.response
    message = response["choices"][0]["message"]

    assert event.call.request == json.loads(recorded.requests[0])
    assert json.loads(message["content"]) == recorded.answer
    assert message["reasoning"].startswith("I am the fake vLLM")


def test_a_run_that_called_tools_keeps_each_call_and_what_it_returned(run: Run):
    run("cell test-tools qwen3-8b-awq@fake", "run case-1")

    [sample] = log_of().samples or []
    calls = [
        message.tool_calls[0].function
        for message in sample.messages
        if isinstance(message, ChatMessageAssistant) and message.tool_calls
    ]

    assert [message.role for message in sample.messages] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
    ]
    assert calls == ["sentinel_string", "sentinel_op"]
    assert [m.text for m in sample.messages if isinstance(m, ChatMessageTool)] == [
        "asdf",
        "0",
    ]
    assert [len(event.input) for event in model_events(sample)] == [1, 3, 5]
    assert (
        sample.output.completion
        == "Fake diagnosis A\nFake diagnosis B\nFake diagnosis C"
    )
    assert set(sample.metadata["tools"]) == {"sentinel_string", "sentinel_op"}


def test_an_errored_run_is_a_sample_with_its_error(run_as: Callable[..., Run]):
    run_as("alex", httpx2.MockTransport(failing))(
        "cell free-text qwen3-8b-awq@fake", "run case-1"
    )

    log = log_of()
    [sample] = log.samples or []

    assert sample.error is not None
    assert "no such model" in sample.error.message
    assert sample.metadata["views"] is None
    assert log.results is not None
    assert log.results.completed_samples == 0


def test_the_log_holds_the_identitys_runs_of_the_cell_alone(
    run_as: Callable[..., Run],
):
    run_as("bob")("cell plan qwen3-8b-awq@fake", "run case-1")
    run_as("alex")(
        "cell free-text qwen3-8b-awq@fake",
        "run case-1",
        "cell plan qwen3-8b-awq@fake",
        "run case-1",
        "run case-2",
    )

    alexs = {
        str(uuid)
        for uuid in RunModel.objects.filter(
            owner__name="alex", trial__configuration__output__isnull=False
        ).values_list("uuid", flat=True)
    }
    samples = log_of().samples or []

    assert [(sample.id, sample.epoch) for sample in samples] == [
        ("case-1", 1),
        ("case-2", 1),
    ]
    assert {sample.metadata["run"] for sample in samples} < alexs
    assert {sample.metadata["output"] for sample in samples} == {"management-plan"}


def test_the_log_goes_where_inspect_looks_for_logs_and_reads_as_a_table(
    run: Run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    run("cell plan qwen3-8b-awq@fake", "run case-1", "run case-2 3")
    monkeypatch.chdir(tmp_path)

    path = write(log_of())
    table: Any = samples_df(str(path))

    assert path.parent == Path("logs")
    assert path.name.endswith(".eval")
    assert read_eval_log(str(path)).eval.task == "cell"
    assert sorted(table["metadata_case"]) == ["case-1", "case-2"]
    assert set(table["metadata_output"]) == {"management-plan"}

    monkeypatch.setenv("INSPECT_LOG_DIR", str(tmp_path / "elsewhere"))

    assert write(log_of()).parent == tmp_path / "elsewhere"
