from typing import Any, cast

import pytest

from chatddx.bench.bench import Bench, NoSecret
from chatddx.bench.cell import Cell
from chatddx.bench.plan import Plan, crossed
from chatddx.conftest import Recommit
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.entity_names import EntityName
from chatddx.runtime.resolution import CellRefused

pytestmark = pytest.mark.django_db


@pytest.fixture
def bench() -> Bench:
    return Bench("alice")


def varied(bench: Bench, **names: list[str]) -> dict[str, list[Any]]:
    """The variations named, by slice; `none` takes the toolset out."""
    return {
        entity: [
            None
            if name == "none"
            else bench.variation_named(cast(EntityName, entity), name)
            for name in listed
        ]
        for entity, listed in names.items()
    }


def labels(cells: list[Cell]) -> list[str]:
    return [cell.label for cell in cells]


def test_the_variations_of_every_slice_are_crossed(bench: Bench):
    cell = bench.cell_of("plan", "qwen3-8b-awq@fake")
    cells = crossed(
        cell,
        varied(bench, reasoning=["off", "on"], sampling=["recommended", "greedy"]),
    )

    # recommended is plan's own, so it sets nothing
    assert labels(cells) == [
        "plan+reasoning=off",
        "plan+reasoning=off+sampling=greedy",
        "plan+reasoning=on",
        "plan+reasoning=on+sampling=greedy",
    ]
    assert all(varied.stack is cell.stack for varied in cells)


def test_a_slice_given_nothing_keeps_the_cell_s_own(bench: Bench):
    cell = bench.cell_of("plan-web", "qwen3-8b-awq@fake")

    assert labels(crossed(cell, {})) == ["plan-web"]
    assert labels(crossed(cell, {"reasoning": []})) == ["plan-web"]
    assert labels(crossed(cell, varied(bench, toolset=["web", "none"]))) == [
        "plan-web",
        "plan-web+toolset=none",
    ]


def test_combinations_that_come_to_one_configuration_are_one_cell(
    bench: Bench, recommit: Recommit
):
    recommit("reasoning", "off", name="off-again", owner="alice")
    cell = bench.cell_of("plan", "qwen3-8b-awq@fake")

    assert labels(crossed(cell, varied(bench, reasoning=["off", "off-again"]))) == [
        "plan+reasoning=off"
    ]


def test_a_plan_holds_back_the_cells_that_can_t_run_and_says_why(
    bench: Bench,
):
    cell = bench.cell_of("baseline", "gpt-oss-20b@fake")
    plan = Plan.of(
        bench, crossed(cell, varied(bench, reasoning=["off", "on"])), ["tag-2"], 5
    )

    assert [ready.cell.label for ready in plan.ready] == ["baseline+reasoning=on"]
    # what runs
    assert plan.description == (
        "baseline+reasoning=on × gpt-oss-20b@fake × 2 cases tagged tag-2"
    )

    [held_back] = plan.held_back

    assert held_back.cell.label == "baseline+reasoning=off"
    assert isinstance(held_back.held_back, CellRefused)
    assert [r.slice for r in held_back.held_back.refusals] == ["reasoning"]
    assert [case.name for case in plan.cases] == ["case-1", "case-2"]


def test_a_cell_without_its_secret_is_held_back_too(bench: Bench):
    for stack in StackBranchModel.objects.filter(name="qwen3-8b-awq@fake"):
        stack.details = {**stack.details, "credential": "fake-key"}
        stack.save()

    plan = Plan.of(bench, [bench.cell_of("plan", "qwen3-8b-awq@fake")], ["tag-1"], 5)

    assert plan.ready == []
    assert isinstance(plan.held_back[0].held_back, NoSecret)
    assert plan.trials == []


def test_trials_go_cell_by_cell_case_by_case_greedy_ones_unseeded(bench: Bench):
    cell = bench.cell_of("free-text", "qwen3-8b-awq@fake")
    plan = Plan.of(
        bench,
        crossed(cell, varied(bench, sampling=["recommended", "greedy"])),
        ["tag-2"],
        42,
    )

    assert [
        (trial.ready.cell.label, trial.called, trial.seed) for trial in plan.trials
    ] == [
        ("free-text", "case-1", 42),
        ("free-text", "case-2", 42),
        ("free-text+sampling=greedy", "case-1", None),
        ("free-text+sampling=greedy", "case-2", None),
    ]
    assert [(kept.label, dict(kept.set), kept.seed) for kept in plan.kept] == [
        ("free-text", {}, 42),
        ("free-text+sampling=greedy", {"sampling": "greedy"}, None),
    ]


def test_a_plan_says_what_it_runs(bench: Bench):
    cell = bench.cell_of("free-text", "qwen3-8b-awq@fake")
    one = Plan.of(bench, [cell], ["tag-1"], None)
    two = Plan.of(
        bench,
        crossed(cell, varied(bench, reasoning=["off", "on"])),
        ["tag-1", "tag-2"],
        None,
    )

    assert one.description == "free-text × qwen3-8b-awq@fake × 1 case tagged tag-1"
    assert two.description == (
        "2 cells of free-text × qwen3-8b-awq@fake × 2 cases tagged tag-1 or tag-2"
    )
