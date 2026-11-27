from dataclasses import replace

import pytest

from chatddx import settings
from chatddx.bench import Bench, NotFound, OverQuota, Replaced, Titled
from chatddx.bench.handles import broken
from chatddx.bench.test.helpers import varying
from chatddx.catalog import Entry, EntryField, Subject, read
from chatddx.catalog.language import language_of
from chatddx.catalog.titles import CaseTitle
from chatddx.curation import Plan
from chatddx.factors.base import Resolver, resolve
from chatddx.factors.scoring import Judge
from chatddx.factors.trial import Execution, Trial
from chatddx.identity import Person
from chatddx.inventory import Inventory
from chatddx.runner import ItemEnded, Refused, RunEvent
from chatddx.runner.gate import admit as admitted
from chatddx.store import Catalog
from chatddx.store.store import Connection
from chatddx.test.world import (
    GPT_OSS,
    GPT_OSS_ARTIFACT,
    LINES,
    LINES_GUIDED,
    QWEN,
    QWEN_ARTIFACT,
    faked,
)


@pytest.mark.usefixtures("fake")
def test_a_run_keeps_its_seeds_cleanup_execution_and_canaries_and_again_too(
    conn: Connection, world: Inventory, alice: Person, plan: Plan
):
    bench = Bench(conn, alice, world)
    variation = bench.variation(LINES)
    probe = plan.named("canary_set", "probe").digest
    cleanup = ("newlines.lf@1", "strip@1")
    running = bench.start(
        variation,
        QWEN,
        [bench.family("crlf").case],
        (3, 5),
        cleanup,
        Execution(concurrency=2),
        probe,
    ).first
    running.send()
    _ = running.finish()

    started = bench.run(running.run)
    trial = resolve(bench.store.get, started.trial, Trial)
    assert (trial.seeds, trial.cleanup) == ((3, 5), cleanup)
    assert (started.execution, started.canaries) == (Execution(concurrency=2), probe)
    assert len(bench.store.run(running.run).items) == 2

    again = bench.again(started, (8,)).started
    repeated = resolve(bench.store.get, again.trial, Trial)
    assert (repeated.seeds, repeated.cleanup) == ((8,), cleanup)
    assert (again.execution, again.canaries) == (started.execution, probe)


@pytest.mark.usefixtures("fake")
def test_a_run_starts_and_runs_again_only_on_cases_its_owner_sees(
    conn: Connection, world: Inventory, alice: Person
):
    bench = Bench(conn, alice, world)
    variation = bench.variation(LINES)
    crlf = bench.family("crlf")
    nowhere = "sha256:" + "0" * 64
    with pytest.raises(NotFound, match=f"no case {nowhere} for alice"):
        _ = bench.start(variation, QWEN, [crlf.case, nowhere], (7,))
    started = bench.start(variation, QWEN, [crlf.case], (7,)).first.started

    archive = bench.people.find("archive")
    assert archive is not None
    unshared = Entry(field=EntryField.COLLABORATOR, person=alice.id, present=False)
    Catalog(conn).note(Subject(family=crlf.id), unshared, archive.id)
    with pytest.raises(NotFound, match=f"no case {crlf.case} for alice"):
        _ = bench.again(started, (8,))
    with pytest.raises(NotFound, match=f"no case {crlf.case} for alice"):
        _ = bench.start(variation, QWEN, [crlf.case], (7,))


@pytest.mark.usefixtures("fake")
def test_a_run_says_what_it_varied_and_running_again_too(
    conn: Connection, world: Inventory, alice: Person
):
    bench = Bench(conn, alice, world)
    named = bench.variation(LINES)
    off = bench.thread("off", "reasoning")[0].digest
    cases = [bench.family("crlf").case]

    plain = bench.start(named, QWEN, cases, (7,)).first.started
    assert varying(bench, plain.run) == (named.configuration, {})
    varied = named.set("reasoning", off, "off")
    started = bench.start(varied, QWEN, cases, (7,)).first.started
    ran = (named.configuration, {"reasoning": off})
    assert varying(bench, started.run) == ran
    assert read.about(bench.rows, Subject(run=started.run)).name == varied.label
    assert varying(bench, bench.again(started, (8,)).run) == ran
    crlf = CaseTitle("crlf", (), False)
    plainly = Titled(LINES, [], QWEN_ARTIFACT, crlf, 1, None, False, (7,))
    assert bench.titled(plain) == plainly
    assert bench.titled(started) == replace(
        plainly, replaced=[Replaced("reasoning", "off")]
    )


def test_a_run_goes_to_the_endpoint_serving_its_model_unless_one_is_named(
    conn: Connection, world: Inventory, alice: Person
):
    bench = Bench(conn, alice, world)
    named = bench.variation(LINES)
    at = bench.endpoint(GPT_OSS)
    gpt_oss, engine = at.model.digest, at.engine
    swapped = named.set("model", gpt_oss, GPT_OSS_ARTIFACT)
    cases = [bench.family("crlf").case]

    with faked(world, bench.store.get, GPT_OSS):
        started = bench.start(swapped, None, cases, (7,)).first.started
    assert started.endpoint is not None and started.endpoint.name == GPT_OSS
    assert resolve(bench.store.get, started.trial, Trial).engine == engine
    assert varying(bench, started.run) == (named.configuration, {"model": gpt_oss})
    titled = bench.titled(started)
    assert (titled.name, titled.replaced, titled.at) == (LINES, [], GPT_OSS_ARTIFACT)
    with pytest.raises(ValueError, match=f"endpoint '{QWEN}' serves another model"):
        _ = bench.start(swapped, QWEN, cases, (7,))

    endpoints = dict(world.endpoints)
    endpoints["twin@fake"] = endpoints[GPT_OSS]
    twice = Bench(conn, alice, world.model_copy(update={"endpoints": endpoints}))
    assert broken(twice.rows, twice.inventory) == [
        f"endpoints {GPT_OSS}, twin@fake serve the same weights, which one endpoint should"
    ]
    twin = twice.at(swapped, "twin@fake")
    assert (twin.name, twin.engine) == ("twin@fake", engine)


def test_a_run_holds_its_cases_times_its_seeds_in_items(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "ITEMS_PER_RUN", 3)
    variation = bench.variation(LINES)
    cases = [bench.family(name).case for name in ("crlf", "bom")]
    with pytest.raises(OverQuota, match="at most 3 items, not 4"):
        _ = bench.start(variation, QWEN, cases, (1, 2))


@pytest.mark.usefixtures("fake")
def test_a_person_resumes_their_own_unfinished_run(
    conn: Connection, world: Inventory, alice: Person, bob: Person
):
    bench = Bench(conn, alice, world)
    variation = bench.variation(LINES)
    cases = [bench.family(name).case for name in ("crlf", "bom")]
    running = bench.start(variation, QWEN, cases, (7,)).first

    def stop(event: RunEvent) -> None:
        if isinstance(event, ItemEnded):
            running.stop()

    running.send(stop)
    others = Bench(conn, bob, world)
    with pytest.raises(NotFound, match=f"no run {running.run} of yours"):
        _ = others.resume(others.run(running.run))

    resumed = bench.resume(bench.run(running.run))
    resumed.send()
    _ = resumed.finish()
    assert len(bench.store.run(running.run).items) == 2


@pytest.mark.usefixtures("fake")
def test_a_run_takes_its_sources_cleanup_and_its_endpoint_s_canaries_and_execution(
    conn: Connection, world: Inventory, alice: Person, plan: Plan
):
    probe = plan.named("canary_set", "probe").digest
    execution = Execution(timeout_s=60, retries=1)
    sources = dict(world.sources)
    sources["test"] = sources["test"].model_copy(
        update={"cleanup": ("strip@1", "newlines.lf@1")}
    )
    endpoints = dict(world.endpoints)
    endpoints[QWEN] = endpoints[QWEN].model_copy(
        update={"canaries": probe, "execution": execution}
    )
    declared = world.model_copy(update={"sources": sources, "endpoints": endpoints})
    bench = Bench(conn, alice, declared)
    variation = bench.variation(LINES)
    cases = [bench.family("crlf").case]

    started = bench.start(variation, QWEN, cases, (7,)).first.started
    trial = resolve(bench.store.get, started.trial, Trial)
    assert trial.cleanup == ("newlines.lf@1", "strip@1")
    assert (started.execution, started.canaries) == (execution, probe)

    given = bench.start(
        variation, QWEN, cases, (7,), (), Execution(), probe
    ).first.started
    assert resolve(bench.store.get, given.trial, Trial).cleanup == ()
    assert given.execution == Execution()


@pytest.mark.usefixtures("fake")
def test_a_start_runs_each_language_its_cases_are_in_and_leaves_out_the_rest(
    conn: Connection,
    world: Inventory,
    alice: Person,
    monkeypatch: pytest.MonkeyPatch,
):
    bench = Bench(conn, alice, world)
    crlf, svenska, nfd, bom = (
        bench.family(name).case for name in ("crlf", "svenska", "nfd", "bom")
    )
    cases = [crlf, svenska, nfd, bom]
    guided = bench.variation(LINES_GUIDED)
    started = bench.start(guided, QWEN, cases, (7,))
    [(english, first), (swedish, second)] = started.runs
    assert started.left_out == []
    assert (english.language, english.translated, english.cases) == (
        "en",
        False,
        [crlf, bom],
    )
    assert (swedish.language, swedish.translated, swedish.cases) == (
        "sv",
        True,
        [svenska, nfd],
    )
    assert english.skeleton is not None and swedish.skeleton is not None
    assert english.skeleton.digest == guided.configuration.digest
    translated = resolve(bench.store.get, second.started.trial, Trial).skeleton
    assert translated == swedish.skeleton.digest != english.skeleton.digest
    assert language_of(bench.rows, translated) == "sv"
    said = [read.about(bench.rows, Subject(run=r.run)) for r in (first, second)]
    assert (said[0].started_with, said[1].started_with) == (
        None,
        first.run,
    )
    assert varying(bench, second.run) == varying(bench, first.run)
    joined = bench.start(guided, QWEN, cases, (7,), joining=first.run)
    assert [
        read.about(bench.rows, Subject(run=r.run)).started_with for _, r in joined.runs
    ] == [first.run, first.run]
    assert bench.described(second.started) == (
        f"{LINES_GUIDED} × {QWEN_ARTIFACT} × 2 cases, in sv, translated (greedy)"
    )
    assert (
        bench.described(first.started)
        == f"{LINES_GUIDED} × {QWEN_ARTIFACT} × 2 cases (greedy)"
    )

    lines = bench.variation(LINES)
    plain = bench.start(lines, QWEN, cases, (7,))
    [(sent, _)] = plain.runs
    [left] = plain.left_out
    assert sent.cases == [crlf, bom]
    assert (left.language, left.cases, left.refused) == (
        "sv",
        [svenska, nfd],
        "lines has no translation into sv",
    )
    with pytest.raises(ValueError, match="lines has no translation into sv"):
        _ = bench.start(lines, QWEN, [svenska, nfd], (7,))

    monkeypatch.setattr(settings, "RUNS_PER_DAY", 6)
    with pytest.raises(OverQuota, match="over the day.s quota: 7 of 6"):
        _ = bench.start(guided, QWEN, cases, (7,))


@pytest.mark.usefixtures("fake")
def test_a_start_one_of_whose_runs_the_gate_refuses_begins_none(
    conn: Connection,
    world: Inventory,
    alice: Person,
    monkeypatch: pytest.MonkeyPatch,
):
    bench = Bench(conn, alice, world)
    cases = [bench.family(name).case for name in ("crlf", "svenska")]
    calls: list[str] = []

    def admit(
        inventory: Inventory,
        get: Resolver,
        endpoint: str,
        trial: Trial,
        judged: tuple[Judge, str] | None = None,
    ):
        calls.append(trial.digest)
        if len(calls) == 2:
            raise Refused("the second is refused")
        return admitted(inventory, get, endpoint, trial, judged)

    monkeypatch.setattr("chatddx.runner.run.admit", admit)
    with pytest.raises(Refused, match="the second is refused"):
        _ = bench.start(bench.variation(LINES_GUIDED), QWEN, cases, (7,))
    assert len(calls) == 2
    assert bench.runs() == []
