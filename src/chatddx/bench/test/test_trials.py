import pytest

from chatddx.bench import Bench, NotFound
from chatddx.catalog.language import language_of
from chatddx.factors.base import resolve
from chatddx.factors.trial import Trial, replicates
from chatddx.identity import Person
from chatddx.inventory import Inventory
from chatddx.store.store import Connection
from chatddx.test.world import JUDGE, LINES, LINES_GUIDED, QWEN


def composed(bench: Bench, configuration: str, *families: str) -> Trial:
    held = bench.skeleton(bench.variation(configuration))
    return Trial(
        skeleton=held.digest,
        engine=bench.endpoint(QWEN).engine,
        cases=tuple(bench.family(f).case for f in families),
        seeds=replicates(held, (7,)),
    )


@pytest.mark.slow
def test_a_trial_is_held_in_its_cases_language(bench: Bench) -> None:
    guided = bench.variation(LINES_GUIDED)
    written = bench.new(composed(bench, LINES_GUIDED, "svenska", "nfd"), "swedish")
    held = resolve(bench.store.get, written.edit.digest, Trial)
    assert held.skeleton == bench.skeleton(guided, "sv").digest
    assert language_of(bench.rows, written.edit.digest) == "sv"
    again = bench.new(held, "swedish again")
    assert again.edit.digest == written.edit.digest

    english = composed(bench, LINES_GUIDED, "crlf")
    back = held.model_copy(update={"cases": english.cases})
    edited = bench.edit(written.edit.thread, written.edit.id, back)
    carried = resolve(bench.store.get, edited.edit.digest, Trial)
    assert carried.skeleton == guided.configuration.digest
    assert bench.check(back).digest == edited.edit.digest


def test_a_trial_s_cases_are_in_one_language_its_skeleton_goes_into(
    bench: Bench,
) -> None:
    refused = [
        (
            composed(bench, LINES_GUIDED, "crlf", "svenska"),
            "a trial's cases are in one language, not in en, sv",
        ),
        (composed(bench, LINES, "svenska"), "has no translation into sv"),
        (composed(bench, JUDGE, "crlf"), "judge skeleton"),
    ]
    for trial, said in refused:
        with pytest.raises(ValueError, match=said):
            _ = bench.new(trial, "refused")
    unseen = composed(bench, LINES, "crlf").model_copy(
        update={"cases": ("sha256:" + "0" * 64,)}
    )
    with pytest.raises(NotFound, match="no case sha256:0+ for alice"):
        _ = bench.new(unseen, "unseen")


def test_a_trial_is_started_only_where_its_engine_is_served(bench: Bench) -> None:
    written = bench.new(composed(bench, LINES, "crlf"), "english")
    unserved = bench.inventory.model_copy(update={"endpoints": {}})
    elsewhere = Bench(bench.conn, bench.person, unserved)
    with pytest.raises(
        ValueError, match="english is out of date: update it on its page"
    ):
        _ = elsewhere.start_trials([written.edit.id])
    with pytest.raises(ValueError, match="a start runs one trial or more"):
        _ = bench.start_trials([])
    lines = bench.variation(LINES).configuration
    with pytest.raises(NotFound, match=f"no trial {lines.thread} for alice"):
        _ = bench.start_trials([lines.id])


@pytest.mark.usefixtures("fake")
def test_a_concurrency_past_the_endpoint_s_capacity_is_what_it_takes(
    conn: Connection, world: Inventory, alice: Person
) -> None:
    bench = Bench(conn, alice, world)
    written = bench.new(composed(bench, LINES, "crlf"), "english")
    [run] = bench.start_trials([written.edit.id], 10_000)
    assert run.started.endpoint is not None
    endpoint = bench.inventory.endpoint(run.started.endpoint.name)
    assert run.started.execution.concurrency == endpoint.capacity
