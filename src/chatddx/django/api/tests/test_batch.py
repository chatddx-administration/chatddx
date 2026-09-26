# pyright: basic
from collections.abc import Callable
from typing import Any

import pytest
from django.test import Client

from chatddx.dev.fake_vllm import FakeTransport
from chatddx.django.api.tests.conftest import Events, events, of
from chatddx.history.models import RunModel, TrialModel
from chatddx.repl.bench import SEEDS
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import CaseBranchDetails
from chatddx.repo.entities.tool.django import ToolBranchModel
from chatddx.repo.store.branch import commit

pytestmark = pytest.mark.django_db

FREE_TEXT = {"configuration": "free-text", "stack": "qwen3-8b-awq@fake"}


def post(client: Client, **spec: Any) -> Any:
    return client.post("/api/batch", spec, content_type="application/json")


@pytest.fixture
def batch(alex: Client, fake: FakeTransport) -> Callable[..., Events]:
    def batch(**spec: Any) -> Events:
        response = post(alex, **spec)
        assert response.status_code == 200, response.content
        assert response["Content-Type"] == "text/event-stream"
        return events(b"".join(response.streaming_content))

    return batch


def test_batch_runs_each_case_with_any_of_the_tags_and_sums_them_up(
    batch: Callable[..., Events], fake: FakeTransport
):
    said = batch(**FREE_TEXT, tags=["tag-2"], seed=42)
    [batched] = of(said, "batch")
    [summary] = of(said, "summary")

    assert said[0] == batched
    assert batched["description"] == (
        "free-text × qwen3-8b-awq@fake × 2 cases tagged tag-2"
    )
    assert (batched["cases"], batched["seed"]) == (["case-1", "case-2"], 42)
    assert [event["case"] for event in of(said, "run")] == ["case-1", "case-2"]
    assert [event["run"]["case"]["name"] for event in of(said, "recorded")] == [
        "case-1",
        "case-2",
    ]
    assert [request["seed"] for request in fake.requests] == [42, 42]
    assert said[-1] == summary
    assert summary["runs"] == 2
    assert {row["scorer"]: row["scores"] for row in summary["scorers"]} == {
        "first_mention": 2,
        "reciprocal_rank": 2,
    }


def test_a_batch_draws_one_seed_for_all_its_cases_unless_told_otherwise(
    batch: Callable[..., Events], fake: FakeTransport
):
    seed = batch(**FREE_TEXT, tags=["tag-2"])[0]["seed"]

    assert 0 <= seed < SEEDS
    assert [request["seed"] for request in fake.requests] == [seed, seed]

    unseeded = batch(**FREE_TEXT, tags=["tag-1"], seed="none")

    assert unseeded[0]["seed"] is None
    assert "seed" not in fake.requests[-1]


def test_a_case_run_again_under_the_batch_s_seed_is_its_trial_again(
    alex: Client, batch: Callable[..., Events]
):
    _ = batch(**FREE_TEXT, tags=["tag-1"], seed=5)
    again = alex.post(
        "/api/runs",
        {**FREE_TEXT, "case": "case-1", "seed": 5, "stream": False},
        content_type="application/json",
    )

    assert again.json()["number"] == 2
    assert TrialModel.objects.count() == 1


def test_a_vignette_under_two_names_runs_once(
    batch: Callable[..., Events], fake: FakeTransport
):
    case = CaseBranchModel.objects.filter(owner__name="archive", name="case-1").latest(
        "pk"
    )
    _ = commit(
        case.trail, CaseBranchDetails(name="case-1-again", owner="alex", tags=["tag-1"])
    )

    said = batch(**FREE_TEXT, tags=["tag-1"])

    assert said[0]["cases"] == ["case-1"]
    assert len(fake.requests) == 1


def test_a_batch_sends_nothing_for_what_it_can_t_run(alex: Client, fake: FakeTransport):
    untagged = post(alex, **FREE_TEXT, tags=[])
    nowhere = post(alex, **FREE_TEXT, tags=["nowhere"])
    half = post(alex, configuration="free-text", tags=["tag-1"])
    refused = post(
        alex,
        configuration="baseline",
        stack="gpt-oss-20b@fake",
        reasoning="off",
        tags=["tag-1"],
    )
    greedy = post(alex, **FREE_TEXT, sampling="greedy", tags=["tag-1"], seed=42)

    assert untagged.status_code == 422
    assert (nowhere.status_code, nowhere.json()) == (
        404,
        {"detail": "no case tagged nowhere for alex"},
    )
    assert half.status_code == 400
    assert refused.status_code == 422
    assert [row["slice"] for row in refused.json()["refusals"]] == ["reasoning"]
    assert greedy.status_code == 422
    assert "sampling is greedy" in greedy.json()["detail"]
    assert fake.requests == []
    assert not RunModel.objects.exists()


def test_a_tool_with_nothing_to_run_stops_the_batch_before_it_begins(
    alex: Client, fake: FakeTransport
):
    _ = ToolBranchModel.objects.filter(name="sentinel_op").update(details={})

    response = post(
        alex, configuration="test-tools", stack="qwen3-8b-awq@fake", tags=["tag-2"]
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "the tool 'sentinel_op' has nothing to run"
    assert fake.requests == []


def test_greedy_sampling_batches_unseeded(
    batch: Callable[..., Events], fake: FakeTransport
):
    said = batch(**FREE_TEXT, sampling="greedy", tags=["tag-1"])

    assert said[0]["seed"] is None
    assert "seed" not in fake.requests[0]
    assert of(said, "recorded")[0]["run"]["seed"] is None
