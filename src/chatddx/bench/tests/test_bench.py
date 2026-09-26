from dataclasses import replace

import pytest

from chatddx.bench.bench import Bench, Drifted, Incomplete, NoSecret, NotOwn, Trial
from chatddx.bench.cell import Cell
from chatddx.conftest import Recommit
from chatddx.core.models import IdentityModel
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.store.branch import BranchNotFoundError
from chatddx.runtime.resolution import CellRefused

pytestmark = pytest.mark.django_db


@pytest.fixture
def bench() -> Bench:
    return Bench("alice")


def test_a_cell_is_put_together_from_names_as_use_on_and_set_would(bench: Bench):
    cell = bench.cell_of(
        "plan", "qwen3-8b-awq@fake", {"reasoning": "off", "toolset": "none"}
    )

    assert cell.label == "plan+reasoning=off"
    assert cell.stack is not None and cell.stack.name == "qwen3-8b-awq@fake"
    assert cell.slices.reasoning.effort == "off"
    assert cell.slices.toolset is None


def test_what_a_cell_can_t_hold_is_said_before_anything_is_put_in(bench: Bench):
    with pytest.raises(ValueError, match="no configuration to set its reasoning in"):
        _ = bench.cell_of(stack="qwen3-8b-awq@fake", variations={"reasoning": "off"})

    with pytest.raises(ValueError, match="only a toolset can be none"):
        _ = bench.cell_of("plan", variations={"reasoning": "none"})

    with pytest.raises(BranchNotFoundError):
        _ = bench.cell_of("plan", "nowhere@fake")


def test_a_cell_never_changes_each_change_is_another(bench: Bench):
    plan = bench.cell_of("plan", "qwen3-8b-awq@fake")
    off = plan.set("reasoning", bench.variation_named("reasoning", "off"))
    back = off.set("reasoning", bench.variation_named("reasoning", "default"))

    assert (plan.label, off.label, back.label) == (
        "plan",
        "plan+reasoning=off",
        "plan",
    )
    assert plan.fingerprint == back.fingerprint != off.fingerprint


def test_a_kept_cell_comes_back_as_it_was_or_not_at_all(bench: Bench):
    cell = bench.cell_of("plan", "qwen3-8b-awq@fake", {"reasoning": "off"})
    kept = cell.kept(42)

    assert (kept.configuration, kept.stack, dict(kept.set), kept.label) == (
        "plan",
        "qwen3-8b-awq@fake",
        {"reasoning": "off"},
        "plan+reasoning=off",
    )
    assert (kept.fingerprint, kept.seed) == (cell.fingerprint, 42)
    assert bench.cell_as_kept(kept).fingerprint == cell.fingerprint

    with pytest.raises(Drifted, match=r"plan\+reasoning=off is another configuration"):
        _ = bench.cell_as_kept(replace(kept, fingerprint="cddx-trail/1:sha256:0"))


def test_a_stack_takes_as_many_jobs_at_once_as_its_details_say(bench: Bench):
    assert bench.max_jobs("qwen3-8b-awq@fake") == 4
    assert bench.max_jobs("qwen3-8b-awq@pelle") == 1


def test_a_ready_cell_is_resolved_with_its_tools(bench: Bench):
    ready = bench.ready(bench.cell_of("test-tools", "qwen3-8b-awq@fake"))

    assert ready.resolution.served_name == "Qwen/Qwen3-8B-AWQ"
    assert list(ready.tools) == ["sentinel_string", "sentinel_op"]
    assert not ready.greedy
    assert bench.ready(bench.cell_of("baseline", "qwen3-8b-awq@fake")).cell


def test_what_stands_in_a_cell_s_way_is_one_of_a_few(bench: Bench, recommit: Recommit):
    recommit("configuration", "plan", owner="bob", collaborators=["alice"])

    with pytest.raises(Incomplete, match="needs a configuration and a stack"):
        _ = bench.ready(Cell().using(bench.configuration_named("plan"), "plan"))

    with pytest.raises(NotOwn, match="bob/plan is bob's: save it as your own first"):
        _ = bench.ready(bench.cell_of("bob/plan", "qwen3-8b-awq@fake"))

    with pytest.raises(CellRefused) as refused:
        _ = bench.ready(
            bench.cell_of("baseline", "gpt-oss-20b@fake", {"reasoning": "off"})
        )

    assert [refusal.slice for refusal in refused.value.refusals] == ["reasoning"]

    for stack in StackBranchModel.objects.filter(name="qwen3-8b-awq@fake"):
        stack.details = {**stack.details, "credential": "fake-key"}
        stack.save()

    with pytest.raises(NoSecret, match="alice has no secret 'fake-key'"):
        _ = bench.ready(bench.cell_of("plan", "qwen3-8b-awq@fake"))

    alice = IdentityModel.objects.get(name="alice")
    alice.secrets = {"fake-key": "sesame"}
    alice.save()

    assert bench.ready(bench.cell_of("plan", "qwen3-8b-awq@fake")).api_key == "sesame"


def test_a_trial_is_a_ready_cell_on_a_case_with_a_seed(bench: Bench):
    ready = bench.ready(bench.cell_of("free-text", "qwen3-8b-awq@fake"))
    [case] = [case for case in bench.cases() if case.name == "case-1"]
    trial = Trial.on(ready, case, 42)

    assert (trial.called, trial.vignette, trial.seed) == (
        "case-1",
        "case vignette 1",
        42,
    )
    assert trial.description == "free-text × qwen3-8b-awq@fake × case-1 (seed 42)"
    assert Trial.on(ready, case, None).description.endswith("× case-1")
    assert bench.made(trial).seed == 42
