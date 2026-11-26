from uuid import UUID

import pytest

from chatddx.bench import Bench
from chatddx.factors.base import resolve
from chatddx.factors.engine import model_of
from chatddx.factors.gathering import REVIEW, Center, Gathering
from chatddx.factors.trial import Trial
from chatddx.identity import Person
from chatddx.inventory import Inventory
from chatddx.store.store import Connection
from chatddx.test.world import LINES, LINES_GUIDED, QWEN


def started(bench: Bench, configuration: str, case: str, *seeds: int) -> UUID:
    variation = bench.variation(configuration)
    return bench.start(variation, QWEN, [case], seeds).first.run


def seedings(held: Gathering | None) -> list[dict[str, UUID]]:
    assert held is not None
    return [{s: g.run for s, g in group.items()} for group in held.groups()]


@pytest.mark.usefixtures("fake")
def test_a_gathering_groups_the_runs_about_a_center_by_configuration(
    conn: Connection, world: Inventory, alice: Person
) -> None:
    bench = Bench(conn, alice, world)
    crlf, bom = bench.family("crlf").case, bench.family("bom").case
    lines = started(bench, LINES, crlf, 11, 12, 13)
    repeated = started(bench, LINES, crlf, 13)
    guided = started(bench, LINES_GUIDED, crlf, 21, 22, 23)
    elsewhere = started(bench, LINES, bom, 31, 32, 33)

    held = bench.gathering(Center(component=crlf), REVIEW)
    assert sorted(seedings(held), key=len) == [
        {"original": guided},
        {"original": lines, "repeat": repeated},
    ]
    assert held is not None
    referred = bench.store.load([g.trial for g in held.gathered])
    assert held.cross_check(referred.get) == []

    trial = resolve(bench.store.get, bench.run(lines).trial, Trial)
    model = model_of(trial.engine, bench.store.get).digest
    every = seedings(bench.gathering(Center(component=model), REVIEW))
    assert {"original": elsewhere} in every
    assert {"original": lines, "repeat": repeated} not in every
    assert seedings(bench.gathering(Center(seed=12), REVIEW)) == [{"original": lines}]
    assert bench.gathering(Center(seed=99), REVIEW) is None
    alone = bench.gathering(Center(component=crlf), REVIEW, started_with=lines)
    assert seedings(alone) == [{"original": lines}]
    among = bench.gathering(Center(component=crlf), REVIEW, among={guided})
    assert seedings(among) == [{"original": guided}]
