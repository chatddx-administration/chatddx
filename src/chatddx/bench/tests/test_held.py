from uuid import uuid4

import pytest

from chatddx.bench.bench import Bench
from chatddx.bench.held import held
from chatddx.bench.plan import Plan, crossed
from chatddx.dev.fake_vllm import FakeTransport
from chatddx.repo.store.branch import get_visible_branch_model
from chatddx.worker import queue, worker

pytestmark = pytest.mark.django_db


def test_what_holds_a_record_is_counted_in_one_place(fake: FakeTransport):
    bench = Bench("alice")
    off = bench.variation_named("reasoning", "off")
    cell = bench.cell_of("free-text", "qwen3-8b-awq@fake")
    plan = Plan.of(bench, crossed(cell, {"reasoning": [off]}), ["tag-2"], 42)
    _ = queue.put("alice", uuid4(), plan.trials)
    case = get_visible_branch_model("case", "alice", "case-1")

    planned = held("alice", "reasoning", [off.trail.id])

    assert (planned.runs, planned.jobs, planned.scores, planned.configurations) == (
        0,
        2,
        0,
        [],
    )
    assert planned and not held("alice", "reasoning", [])

    assert worker.run(fake) == 2
    assert bench.save(cell, "mine")

    ran = held("alice", "reasoning", [off.trail.id])
    of_case = held("alice", "case", [case.trail_id], [case.pk])
    instruction = held("alice", "instruction", [cell.variation("instruction").id])

    assert (ran.runs, ran.jobs) == (2, 2)
    assert (of_case.runs, of_case.jobs) == (1, 1)
    assert instruction.runs == 2
    assert [each.name for each in instruction.configurations] == ["mine"]
