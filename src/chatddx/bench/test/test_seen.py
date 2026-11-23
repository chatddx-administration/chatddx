from uuid import UUID

import pytest
from pydantic import JsonValue

from chatddx.bench import (
    Ambiguous,
    Bench,
    Conflict,
    Graded,
    MovedOn,
    NotFound,
    ScorerStarted,
    ScoringEvent,
)
from chatddx.bench.seen import scoring
from chatddx.bench.test.helpers import another_expectation, ran, trial
from chatddx.catalog import About, Edit, Entry, EntryField, Subject, read, threads
from chatddx.curation import Plan, load_cases
from chatddx.factors.base import StructuralError, resolve
from chatddx.factors.bundle import Registry
from chatddx.factors.engine import FileDigest, LocalEngine, LocalModel, model_of
from chatddx.factors.request import Prompt
from chatddx.factors.scoring import Expectation, Judge, View
from chatddx.identity import Person, owns
from chatddx.inventory import World
from chatddx.runner import Halt, Runner
from chatddx.store import Catalog, People, Rows, Store
from chatddx.store.store import Connection
from chatddx.test.world import (
    DATA,
    GPT_OSS,
    GPT_OSS_ARTIFACT,
    LINES,
    LINES_GUIDED,
    MISTRAL,
    MISTRAL_ARTIFACT,
    MISTRAL_MODEL,
    NATIVE,
    QWEN,
    QWEN_ARTIFACT,
    QWEN_BARE,
    QWEN_BARE_ARTIFACT,
    QWEN_MODEL,
    REMOTE,
    TEST,
    TOOL_ANSWER,
    UNKNOWN_MODEL,
)


def test_a_person_sees_their_own_and_shared_threads_and_families(
    conn: Connection, alice: Person, bob: Person, bench: Bench
) -> None:
    owners = {a.owner for _, a in bench.threads("configuration")}
    archive = People(conn).find("archive")
    assert archive is not None and owners == {alice.id, archive.id}

    mine, about = bench.thread(LINES, "configuration")
    assert about.owner == alice.id
    theirs, about = bench.thread(f"archive/{LINES}", "configuration")
    assert about.owner == archive.id
    assert theirs.digest == mine.digest and theirs.thread != mine.thread
    with pytest.raises(NotFound, match="no configuration 'nothing' for alice"):
        _ = bench.thread("nothing", "configuration")

    families, cases = bench.families(), load_cases(DATA)
    assert len(families) == len(cases)
    assert {f.about.language for f in families} == {c.language for c in cases.values()}
    assert {f.name: f.about.tags for f in families} == {
        name: set(c.tags) for name, c in cases.items()
    }
    assert all(f.about.tags for f in families)
    bobs = Bench(conn, bob, bench.inventory)
    assert bobs.threads("configuration") == [] and bobs.families() == []


def test_a_case_is_found_by_its_name_or_as_owner_slash_name(bench: Bench) -> None:
    found = bench.family("noted")
    assert bench.family("archive/noted") == found
    with pytest.raises(NotFound, match="no case 'alice/noted' for alice"):
        _ = bench.family("alice/noted")
    with pytest.raises(NotFound, match="no case 'nope' for alice"):
        _ = bench.family("nope")


def test_threads_cases_and_runs_are_found_by_id_among_what_the_person_sees(
    conn: Connection, alice: Person, bob: Person, bench: Bench, plan: Plan
) -> None:
    mine, _ = bench.thread(LINES, "configuration")
    assert bench.thread(mine.thread) == bench.thread(LINES, "configuration")
    assert bench.thread(mine.thread, "configuration")[0] == mine
    with pytest.raises(NotFound, match=f"no reasoning {mine.thread} for alice"):
        _ = bench.thread(mine.thread, "reasoning")
    with pytest.raises(NotFound, match="no thread 0 for alice"):
        _ = bench.thread(0)
    bobs = Bench(conn, bob, bench.inventory)
    with pytest.raises(NotFound, match=f"no thread {mine.thread} for bob"):
        _ = bobs.thread(mine.thread)
    Catalog(conn).note(
        Subject(thread=mine.thread), Entry(field=EntryField.DELETED), alice.id
    )
    with pytest.raises(NotFound):
        _ = bench.thread(mine.thread)

    family = bench.family("noted")
    assert bench.family(family.id) == family
    with pytest.raises(NotFound, match=f"no case {family.id} for bob"):
        _ = bobs.family(family.id)
    with pytest.raises(NotFound, match="no case 0 for alice"):
        _ = bench.family(0)

    made = trial(conn, plan, LINES, "crlf")
    own, theirs = ran(conn, alice, made), ran(conn, bob, made)
    assert bench.run(own).run == own
    with pytest.raises(NotFound, match=f"no run {theirs} of yours"):
        _ = bench.run(theirs)


def test_a_variation_is_made_from_a_configuration_s_id_and_digests(
    bench: Bench,
) -> None:
    named = bench.variation(LINES)
    off = bench.thread("off", "reasoning")[0].digest
    thread = named.configuration.thread

    assert bench.variation(thread) == named
    varied = bench.variation(thread, {"reasoning": off})
    assert bench.skeleton(varied) == bench.skeleton(named.set("reasoning", off, "off"))
    with pytest.raises(ValueError, match="isn't a stored chunk of prompt"):
        _ = bench.variation(thread, {"prompt": off})
    with pytest.raises(ValueError, match="isn't a stored model"):
        _ = bench.variation(thread, {"model": off})
    with pytest.raises(ValueError, match="no part 'stack'"):
        _ = bench.variation(thread, {"stack": off})
    with pytest.raises(ValueError, match="always holds its prompt"):
        _ = bench.variation(thread, {"prompt": None})
    chunk = bench.thread("off", "reasoning")[0].thread
    with pytest.raises(NotFound, match=f"no configuration {chunk} for alice"):
        _ = bench.variation(chunk)


def test_a_person_finds_their_runs_and_those_that_reach_a_digest(
    conn: Connection, alice: Person, bob: Person, bench: Bench, plan: Plan
) -> None:
    lines = trial(conn, plan, LINES, "crlf", "svenska")
    native = trial(conn, plan, NATIVE, "crlf")
    first = ran(conn, alice, lines)
    second = ran(conn, alice, native)
    bobs = ran(conn, bob, lines)
    gone = ran(conn, alice, native)
    Catalog(conn).note(Subject(run=gone), Entry(field=EntryField.DELETED), alice.id)

    assert [r.run for r in bench.runs()] == [second, first]
    assert bench.run().run == second
    assert bench.run(str(first)[:8]).run == first
    with pytest.raises(Ambiguous, match="2 runs of yours start with ''"):
        _ = bench.run("")
    with pytest.raises(NotFound, match="no run of yours"):
        _ = bench.run("zzz")

    assert [r.run for r in bench.runs(reaching=lines.skeleton)] == [first]
    output = plan.named("output", "lines").digest
    assert [r.run for r in bench.runs(reaching=output)] == [first]
    [shared_case] = set(lines.cases) & set(native.cases)
    assert [r.run for r in bench.runs(reaching=shared_case)] == [second, first]
    store = Store(conn)
    started = store.started([first, second, bobs, gone])
    assert {r.run for r in started if r.trial == lines.digest} == {first, bobs}
    assert store.finished([first, second, gone]) == {first, second, gone}


def test_a_view_of_the_whole_answer_is_offered_by_a_text_output_only(
    conn: Connection, alice: Person, bench: Bench, plan: Plan
) -> None:
    whole, picked = View(metric="m"), View(output="$.diagnoses[*]", metric="m")
    schema: JsonValue = {
        "type": "object",
        "properties": {"diagnoses": {"type": "array", "items": {"type": "string"}}},
    }
    assert whole.offered_by(None) and not whole.offered_by(schema)
    assert not View(output="$", metric="m").offered_by(schema)
    assert picked.offered_by(schema) and not picked.offered_by(None)

    started = bench.run(str(ran(conn, alice, trial(conn, plan, NATIVE, "crlf"))))
    assert {a.name for _, a, _ in bench.scorers(started)} == {"answer"}


@pytest.mark.slow
def test_a_run_is_left_to_score_until_scored_under_the_scoring_built_now(
    conn: Connection, alice: Person, bench: Bench, plan: Plan
) -> None:
    made = trial(conn, plan, LINES, "crlf", "svenska")
    run = ran(conn, alice, made)
    _ = ran(conn, alice, made, finished=False)
    started = bench.run(str(run))
    texts = {"lines", "whole", "judged"}
    assert {a.name for _, a, _ in bench.scorers(started)} == texts

    scorer = plan.named("scorer", "lines").digest
    others = {plan.named("scorer", name).digest for name in texts - {"lines"}}
    assert set(bench.unscored(started)) == {scorer, *others}
    assert [(r.run, set(s)) for r, s in bench.outstanding()] == [
        (run, {scorer, *others})
    ]
    built = scoring(bench, started, scorer)
    assert built is not None and len(built.expectations) == 2
    store = Store(conn)
    registry = store.load([scorer, *built.expectations])
    grading = Runner(conn, bench.inventory, alice).score(run, built, registry)
    grading.send()
    _, findings = grading.finish()
    assert findings == []
    assert set(bench.unscored(started)) == others
    assert [s.scoring for s in store.scores_of(run)] == [built.digest]

    catalog = Catalog(conn)
    rows = Rows(conn)
    [thread] = [
        e.thread
        for e, a in threads.expecting(rows, [made.cases[0]])[made.cases[0]]
        if a.owner == alice.id
    ]
    head = resolve(store.get, threads.head(rows, thread).digest, Expectation)
    registry = store.load([head.digest])
    edited = registry.add(
        Expectation(
            case=head.case,
            expectation_schema=head.expectation_schema,
            data={"diagnosis": {"pattern": "sepsis"}},
        )
    )
    _ = store.add(registry, [edited])
    _ = catalog.edit(thread, edited, alice.id)
    assert set(bench.unscored(started)) == {scorer, *others}
    rebuilt = scoring(bench, started, scorer)
    assert rebuilt is not None and edited in rebuilt.expectations


def test_only_a_finished_score_counts_against_what_is_left_to_score(
    conn: Connection, alice: Person, bench: Bench, plan: Plan
) -> None:
    run = ran(conn, alice, trial(conn, plan, LINES, "crlf"))
    started = bench.run(run)
    scorer = plan.named("scorer", "lines").digest
    built = scoring(bench, started, scorer)
    assert built is not None
    registry = Store(conn).load([scorer, *built.expectations])

    grading = Runner(conn, bench.inventory, alice).score(run, built, registry)
    assert scorer in bench.unscored(started)

    _ = grading.finish()
    assert scorer not in bench.unscored(started)
    assert [r.run for r in bench.runs(scored_by=scorer)] == [run]


def test_a_case_is_held_to_the_expectation_scoring_picks(
    conn: Connection, alice: Person, bob: Person, bench: Bench, plan: Plan
) -> None:
    case = bench.family("noted").case
    schema = plan.named("expectation_schema", "targets").digest
    assert bench.expectation_schemas(case) == [schema]

    held = bench.expectation(case, schema)
    assert held is not None
    expecting = threads.expecting(Rows(conn), [case], schema)[case]
    assert [e.digest for e, a in expecting if owns(alice.id, a)] == [held.digest]

    theirs = Bench(conn, bob, bench.inventory)
    assert theirs.expectation_schemas(case) == []
    assert theirs.expectation(case, schema) is None

    catalog = Catalog(conn)
    rows = Rows(conn)
    archive = People(conn).find("archive")
    assert archive is not None
    [shared] = [
        e.thread
        for e, a in threads.expecting(rows, [case])[case]
        if a.owner == archive.id
    ]
    to_bob = Entry(field=EntryField.COLLABORATOR, person=bob.id)
    catalog.note(Subject(thread=shared), to_bob, archive.id)
    assert theirs.expectation_schemas(case) == [schema]
    assert theirs.expectation(case, schema) is None


@pytest.mark.slow
def test_several_expectations_to_choose_from_are_ambiguous(
    conn: Connection, alice: Person, bench: Bench, plan: Plan
) -> None:
    made = trial(conn, plan, LINES, "crlf")
    [case] = made.cases
    _ = another_expectation(bench, case, {"diagnosis": {"pattern": "sepsis"}})
    [schema] = bench.expectation_schemas(case)
    scorer = plan.named("scorer", "lines").digest
    started = bench.run(ran(conn, alice, made))

    with pytest.raises(Ambiguous, match="has expectations to choose from"):
        _ = bench.expectation(case, schema)
    with pytest.raises(Ambiguous, match="has expectations to choose from"):
        _ = scoring(bench, started, scorer)

    assert scorer in bench.unscored(started)
    assert [r.run for r, _ in bench.outstanding()] == [started.run]
    [graded] = bench.score(started, [scorer])
    assert graded.score is None
    assert graded.refused and "has expectations to choose from" in graded.refused
    assert Store(conn).scores_of(started.run) == []

    family = bench.family("crlf")
    variation = bench.variation(LINES)
    [held] = [
        r for r in bench.reach(variation, [family]) if r.offered and r.scorer == "whole"
    ]
    assert (held.choosing, held.missing, held.have) == ([family], [], 0)


def test_a_swapped_model_keeps_every_other_pick_and_works_the_rest_out(
    bench: Bench,
) -> None:
    lines = bench.variation(LINES)
    off = lines.set("reasoning", bench.thread("off", "reasoning")[0].digest, "off")
    gpt_oss = off.set("model", bench.endpoint(GPT_OSS).model.digest, GPT_OSS_ARTIFACT)

    assert gpt_oss.label == f"{LINES}+reasoning=off+model={GPT_OSS_ARTIFACT}"
    assert gpt_oss.held("reasoning") == off.held("reasoning")
    assert bench.skeleton(off).body["chat_template_kwargs"] == {
        "enable_thinking": False
    }
    body = bench.skeleton(gpt_oss).body
    assert (body["reasoning_effort"], body["temperature"]) == ("low", 1.0)
    landed = bench.landed(gpt_oss)
    assert (landed["reasoning"].level, landed["sampling"].level) == ("low", "low")
    assert "always reasons" in landed["reasoning"].nearest[0]
    assert bench.landed(off)["reasoning"].nearest == ()
    assert bench.landed(lines).keys() == {"sampling"}

    on = lines.set("reasoning", bench.thread("on", "reasoning")[0].digest, "on")
    mistral = on.set("model", bench.endpoint(MISTRAL).model.digest, MISTRAL_ARTIFACT)
    with pytest.raises(StructuralError, match=f"{MISTRAL_MODEL}: .*doesn't reason"):
        _ = bench.skeleton(mistral)


def test_a_configuration_is_found_by_its_name(
    bench: Bench,
) -> None:
    variation = bench.variation("native")
    assert (variation.name, variation.label, variation.parts) == (NATIVE, NATIVE, {})
    with pytest.raises(NotFound, match="no configuration 'nope' for alice"):
        _ = bench.variation("nope")


def test_a_variation_compiles_to_a_skeleton_of_its_own(bench: Bench) -> None:
    configuration = bench.variation(LINES)
    off = configuration.set(
        "reasoning", bench.thread("off", "reasoning")[0].digest, "off"
    )

    assert bench.skeleton(configuration).digest == configuration.configuration.digest
    assert bench.skeleton(off).digest != configuration.configuration.digest
    assert bench.skeleton(off).body["chat_template_kwargs"] == {
        "enable_thinking": False
    }


def test_a_variation_s_request_shows_placeholders_for_what_it_is_sent_with(
    bench: Bench,
) -> None:
    engine = bench.endpoint(QWEN).engine
    variation = bench.variation(LINES)

    unplaced = bench.request(variation, None, 7)
    placed = bench.request(variation, engine, 7)
    assert (unplaced["model"], placed["model"]) == ("‹model›", engine)
    assert "‹vignette›" in str(placed["messages"])
    assert placed["seed"] == 7
    with pytest.raises(ValueError, match="not an engine"):
        _ = bench.request(variation, variation.configuration.digest, 7)


def test_several_configurations_of_one_name_are_refused_a_save(bench: Bench) -> None:
    variation = bench.variation(LINES)
    _ = Catalog(bench.conn).create(
        variation.configuration.digest, bench.person.id, name="twice"
    )
    _ = Catalog(bench.conn).create(
        variation.configuration.digest, bench.person.id, name="twice"
    )

    with pytest.raises(Ambiguous, match="2 configurations named 'twice'"):
        _ = bench.save(variation, "twice")


@pytest.mark.slow
def test_a_fork_is_a_new_configuration_and_an_edit_a_new_version_of_one_s_own(
    bench: Bench,
) -> None:
    variation = bench.variation(LINES)
    off = variation.set("reasoning", bench.thread("off", "reasoning")[0].digest, "off")
    rows = Rows(bench.conn)

    lines = variation.configuration.thread
    forked = bench.fork(lines, "terse", off)
    again = bench.fork(lines, "terse", off)
    assert (forked.what, again.what) == ("created", "created")
    thread = forked.edit.thread
    assert thread != again.edit.thread
    assert threads.thread(rows, thread).forked_from == variation.configuration.id
    assert bench.thread(thread)[1].owner == bench.person.id
    assert forked.edit.digest == bench.skeleton(off).digest
    with pytest.raises(ValueError, match="isn't a variation of configuration"):
        _ = bench.fork(thread, "elsewhere", off)

    seen = forked.edit.id
    edited = bench.edit(thread, seen, variation)
    assert (edited.what, bench.thread(thread)[1].name) == ("a new version", "terse")
    now = edited.edit.id
    assert bench.edit(thread, now, variation).what == "unchanged"
    assert [e.digest for e in threads.history(rows, thread)] == [
        forked.edit.digest,
        variation.configuration.digest,
    ]
    with pytest.raises(MovedOn, match=f"since edit {seen}: its head is edit {now}"):
        _ = bench.edit(thread, seen, off)
    with pytest.raises(ValueError, match="holds skeleton components, not chunk"):
        _ = bench.edit(thread, now, bench.store.get(off.held("reasoning") or ""))

    archives = bench.thread(f"archive/{LINES}", "configuration")[0].thread
    with pytest.raises(NotFound, match=f"no configuration {archives} of yours"):
        _ = bench.edit(archives, now, variation)


def test_a_new_recipe_of_the_same_request_is_a_new_version(bench: Bench) -> None:
    variation = bench.variation("headed")
    prompt = resolve(bench.store.get, variation.held("prompt") or "", Prompt)
    head, *rest = prompt.segments
    assert isinstance(head, str)
    split = Prompt(segments=(head[:-1], head[-1], *rest))
    registry = Registry()
    _ = bench.store.add(registry, [registry.add(split)])
    resplit = variation.set("prompt", split.digest, "split")
    skeleton = variation.configuration.digest
    assert bench.skeleton(resplit).digest == skeleton

    forked = bench.fork(variation.configuration.thread, "headed, split")
    thread = forked.edit.thread
    edited = bench.edit(thread, forked.edit.id, resplit)
    history = threads.history(Rows(bench.conn), thread)
    assert edited.what == "a new version"
    assert [e.digest for e in history] == [skeleton, skeleton]
    assert (
        threads.recipe(bench.rows, threads.head(bench.rows, thread)) == resplit.varied
    )
    assert bench.edit(thread, history[-1].id, resplit).what == "unchanged"
    held = bench.holder(skeleton, resplit.varied)
    assert held is not None and held[0].thread == thread
    held = bench.holder(skeleton, variation.varied)
    assert held is not None and held[0].thread != thread


def _expectation_of(rows: Rows, case: str, owner: int) -> int:
    [thread] = [
        e.thread for e, a in threads.expecting(rows, [case])[case] if owns(owner, a)
    ]
    return thread


def test_a_person_takes_the_expectations_shared_with_them(
    conn: Connection, alice: Person, bob: Person, bench: Bench, plan: Plan
) -> None:
    catalog, store = Catalog(conn), Store(conn)
    rows = Rows(conn)
    archive = People(conn).find("archive")
    assert archive is not None
    schema = plan.named("expectation_schema", "targets").digest
    crlf, noted, svenska = (bench.family(n).case for n in ("crlf", "noted", "svenska"))
    gone = Entry(field=EntryField.DELETED)
    for case in (crlf, svenska):
        own = _expectation_of(rows, case, alice.id)
        catalog.note(Subject(thread=own), gone, alice.id)
    kept = _expectation_of(rows, noted, alice.id)

    taken = bench.take([crlf, noted, svenska, crlf], schema)
    assert (taken.kept, taken.choosing, taken.missing) == ({noted: kept}, {}, [])
    assert set(taken.taken) == {crlf, svenska}
    origin = _expectation_of(rows, crlf, archive.id)
    took = threads.thread(rows, taken.taken[crlf])
    assert took.forked_from == threads.head(rows, origin).id
    assert read.about(rows, Subject(thread=took.id)).owner == alice.id
    held = bench.expectation(crlf, schema)
    assert held is not None and held.digest == threads.head(rows, origin).digest

    again = bench.take([crlf, noted, svenska], schema)
    assert again.taken == {} and set(again.kept) == {crlf, noted, svenska}

    catalog.note(Subject(thread=taken.taken[crlf]), gone, alice.id)
    head = resolve(store.get, threads.head(rows, origin).digest, Expectation)
    registry = store.load([head.digest])
    theirs = registry.add(
        Expectation(case=crlf, expectation_schema=schema, data={"diagnosis": "x"})
    )
    _ = store.add(registry, [theirs])
    bobs = catalog.create(theirs, bob.id).thread
    to_alice = Entry(field=EntryField.COLLABORATOR, person=alice.id)
    catalog.note(Subject(thread=bobs), to_alice, bob.id)
    assert bench.take([crlf], schema).choosing == {crlf: [origin, bobs]}
    assert set(bench.take([crlf], schema, owner="archive").taken) == {crlf}

    assert bench.take([crlf], schema, owner="bob").kept == {
        crlf: _expectation_of(rows, crlf, alice.id)
    }
    with pytest.raises(NotFound, match="no person 'nobody'"):
        _ = bench.take([crlf], schema, owner="nobody")
    with pytest.raises(ValueError, match="isn't a stored expectation schema"):
        _ = bench.take([crlf], crlf)


def test_a_person_replaces_their_own_expectation_only_when_they_say_so(
    conn: Connection, alice: Person, bench: Bench, plan: Plan
) -> None:
    rows = Rows(conn)
    archive = People(conn).find("archive")
    assert archive is not None
    schema = plan.named("expectation_schema", "targets").digest
    case = bench.family("noted").case
    mine = _expectation_of(rows, case, alice.id)
    origin = _expectation_of(rows, case, archive.id)

    with pytest.raises(
        Conflict, match=f"has their own .* in thread {mine}: replace it"
    ):
        _ = bench.take_from(origin)
    with pytest.raises(ValueError, match=f"expectation {mine} is yours already"):
        _ = bench.take_from(mine)
    with pytest.raises(NotFound, match="no expectation"):
        _ = bench.take_from(bench.threads("configuration")[0][0].thread)

    took = bench.take_from(origin, replace=True)
    assert read.about(rows, Subject(thread=mine)).deleted
    assert threads.thread(rows, took).forked_from == threads.head(rows, origin).id
    assert bench.shared(case, schema)[0][0].thread == origin
    held = bench.expectation(case, schema)
    assert held is not None and held.digest == threads.head(rows, origin).digest


@pytest.mark.slow
def test_a_judged_scorer_applies_where_the_world_lets_its_judges_run(
    conn: Connection,
    alice: Person,
    bench: Bench,
    plan: Plan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CHATDDX_TEST_REMOTE", raising=False)
    run = ran(conn, alice, trial(conn, plan, LINES, "noted"))
    started = bench.run(str(run))
    applies = {a.name for _, a, _ in bench.scorers(started)}
    assert "judged" in applies and "judged-remote" not in applies
    assert plan.named("scorer", "judged-remote").digest not in bench.unscored(started)

    cleared = bench.inventory.model_copy(
        update={"cleared": bench.inventory.cleared | {REMOTE: ("test",)}}
    )
    opened = Bench(conn, alice, cleared)
    assert "judged-remote" in {a.name for _, a, _ in opened.scorers(started)}
    [refused] = [g for g in opened.score(started) if g.name == "judged-remote"]
    assert refused.refused == (
        f"endpoint {REMOTE!r} needs the secret in $CHATDDX_TEST_REMOTE, which isn't set"
    )


def test_every_handle_is_had_with_the_endpoint_serving_it_or_none(
    conn: Connection, alice: Person, bench: Bench
) -> None:
    served = {
        QWEN_ARTIFACT: QWEN,
        QWEN_BARE_ARTIFACT: QWEN_BARE,
        GPT_OSS_ARTIFACT: GPT_OSS,
        MISTRAL_ARTIFACT: MISTRAL,
        UNKNOWN_MODEL: REMOTE,
    }
    found = bench.handles()
    assert [h.name for h, _ in found] == sorted(served)
    for handle, at in found:
        assert at is not None and at.name == served[handle.name]
        assert model_of(at.engine, bench.store.get).digest == handle.weights

    inventory = bench.inventory
    endpoints = {n: e for n, e in inventory.endpoints.items() if n != QWEN}
    unserved = Bench(conn, alice, inventory.model_copy(update={"endpoints": endpoints}))
    assert {h.name: at for h, at in unserved.handles()}[QWEN_ARTIFACT] is None


def test_a_judged_scoring_pins_its_judges_latest_engines_or_says_why_it_can_t(
    conn: Connection, alice: Person, bench: Bench, plan: Plan
) -> None:
    started = bench.run(ran(conn, alice, trial(conn, plan, LINES, "noted")))
    judged = plan.named("scorer", "judged").digest
    built = scoring(bench, started, judged)
    assert built is not None
    assert {e.engine for e in built.engines} == {bench.endpoint(QWEN).engine}

    inventory = bench.inventory
    endpoints = {n: e for n, e in inventory.endpoints.items() if n != QWEN}
    unserved = Bench(conn, alice, inventory.model_copy(update={"endpoints": endpoints}))
    assert "judged" not in {a.name for _, a, _ in unserved.scorers(started)}
    with pytest.raises(
        ValueError, match=f"no endpoint here serves model {QWEN_ARTIFACT}: pick another"
    ):
        _ = scoring(unserved, started, judged)

    store = Store(conn)
    registry = store.load([inventory.endpoint(QWEN).engine])
    weights = registry.add(
        LocalModel(
            repo=QWEN_MODEL,
            revision="newer",
            files=(FileDigest(path="none", sha256="0" * 64),),
        )
    )
    engine = resolve(registry.get, inventory.endpoint(QWEN).engine, LocalEngine)
    newer = registry.add(engine.model_copy(update={"model": weights}))
    _ = store.add(registry, [newer])
    _ = Catalog(conn).edit(
        bench.handle(bench.endpoint(QWEN).model.digest).thread, weights, alice.id
    )
    moved = dict(inventory.endpoints)
    moved[QWEN] = moved[QWEN].model_copy(update={"engine": newer})
    later = Bench(conn, alice, inventory.model_copy(update={"endpoints": moved}))
    assert "judged" in {a.name for _, a, _ in later.scorers(started)}
    assert judged in later.unscored(started)
    [refused] = later.score(started, {judged})
    assert refused.refused is not None and refused.refused.endswith(
        "is out of date: update it on its page"
    )


def test_a_judge_under_a_deleted_handle_says_to_pick_another(
    conn: Connection, alice: Person, bench: Bench, plan: Plan
) -> None:
    started = bench.run(ran(conn, alice, trial(conn, plan, LINES, "noted")))
    judged = plan.named("scorer", "judged").digest
    handle = bench.handle(bench.endpoint(QWEN).model.digest)
    archive = People(conn).find("archive")
    assert archive is not None
    Catalog(conn).note(
        Subject(thread=handle.thread), Entry(field=EntryField.DELETED), archive.id
    )
    deleted = Bench(conn, alice, bench.inventory)
    held = deleted.handle(handle.weights)
    assert (held.name, held.deleted, deleted.latest(held)) == (
        QWEN_ARTIFACT,
        True,
        None,
    )
    assert "judged" not in {a.name for _, a, _ in deleted.scorers(started)}
    with pytest.raises(
        ValueError, match=f"model {QWEN_ARTIFACT} is deleted: pick another"
    ):
        _ = scoring(deleted, started, judged)


def scored(graded: Graded) -> UUID:
    assert graded.score is not None
    return graded.score.started.score


@pytest.mark.slow
def test_a_run_s_scores_are_read_the_latest_every_one_or_one_by_id(
    conn: Connection, alice: Person, bob: Person, bench: Bench, plan: Plan
) -> None:
    run = ran(conn, alice, trial(conn, plan, LINES, "crlf"))
    other = ran(conn, alice, trial(conn, plan, LINES, "svenska"))
    lines = plan.named("scorer", "lines").digest
    [first] = bench.score(bench.run(run), {lines})
    [second] = bench.score(bench.run(run), {lines})

    started = bench.run(run)
    [latest] = bench.scores_of(started)
    assert (latest.name, scored(latest)) == ("lines", scored(second))
    every = [scored(g) for g in bench.scores_of(started, every=True)]
    assert every == [scored(second), scored(first)]
    assert scored(bench.score_of(started, scored(first))) == scored(first)
    assert bench.title(lines) == "lines"

    with pytest.raises(NotFound, match=f"no score {scored(first)} of run {other}"):
        _ = bench.score_of(bench.run(other), scored(first))
    theirs = Bench(conn, bob, bench.inventory)
    with pytest.raises(NotFound, match=f"no run {run} of yours"):
        _ = theirs.run(run)


def test_a_configuration_is_found_by_the_title_of_its_answer_s_schema(
    bench: Bench,
) -> None:
    def names(found: list[tuple[Edit, About]]) -> set[str | None]:
        return {a.name for _, a in found}

    answering = names(bench.threads("configuration", answering="Answer"))
    assert NATIVE in answering
    assert LINES not in answering and TOOL_ANSWER not in answering
    verdicts = names(bench.threads("configuration", answering="Verdict"))
    judges = names(bench.threads("configuration", purpose="judge"))
    assert verdicts and verdicts <= judges
    assert bench.threads("configuration", answering="nothing") == []
    generation = bench.threads("configuration", purpose="generation")
    assert not verdicts & names(generation)
    with pytest.raises(ValueError, match="only a configuration has a purpose"):
        _ = bench.threads("scorer", answering="Verdict")


def test_a_judge_configuration_is_looked_at_as_a_judge_and_isn_t_run(
    bench: Bench,
) -> None:
    judges = {a.name for _, a in bench.threads("configuration", purpose="judge")}
    generation = {
        a.name for _, a in bench.threads("configuration", purpose="generation")
    }
    assert "judge-graded" in judges and LINES in generation
    assert not judges & generation

    variation = bench.variation("judge-graded")
    engine = bench.endpoint(GPT_OSS).engine
    findings = bench.findings(variation, engine, 7)
    weights = bench.endpoint(GPT_OSS).model.digest
    judge = Judge(skeleton=variation.configuration.digest, model=weights, seeds=(7,))
    assert {f.code for f in findings} == {
        "facts.output_note",
        "facts.sampling_unmatched",
    }
    assert {f.subject for f in findings} == {judge.digest}
    assert bench.reach(variation, bench.families()) == []

    case = bench.family("crlf").case
    with pytest.raises(ValueError, match="is a judge configuration"):
        _ = bench.start(variation, QWEN, [case], (7,))


def test_a_run_runs_again_under_its_handle_or_is_refused_saying_why(
    conn: Connection, alice: Person, plan: Plan
) -> None:
    made = trial(conn, plan, LINES, "crlf")
    run = ran(conn, alice, made, endpoint=QWEN)
    inventory = World.load(TEST).inventory
    endpoints = dict(inventory.endpoints)
    endpoints[QWEN] = endpoints[QWEN_BARE]
    bench = Bench(conn, alice, inventory.model_copy(update={"endpoints": endpoints}))
    handle, latest = bench.under(made.engine)
    assert (None if handle is None else handle.name, latest) == (QWEN_ARTIFACT, False)
    with pytest.raises(
        ValueError, match=f"no endpoint here serves model {QWEN_ARTIFACT}: pick another"
    ):
        _ = bench.again(bench.run(run), (9,))

    store = Store(conn)
    registry = store.load([])
    weights = registry.add(
        LocalModel(
            repo=QWEN_MODEL,
            revision="newer",
            files=(FileDigest(path="none", sha256="0" * 64),),
        )
    )
    _ = store.add(registry, [weights])
    held = Bench(conn, alice, inventory).handle(model_of(made.engine, store.get).digest)
    _ = Catalog(conn).edit(held.thread, weights, alice.id)
    later = Bench(conn, alice, inventory)
    with pytest.raises(
        ValueError, match="is out of date: run its configuration instead"
    ):
        _ = later.again(later.run(run), (9,))


def test_a_scoring_says_each_score_it_starts_and_a_halt_stops_the_rest(
    conn: Connection, alice: Person, bench: Bench, plan: Plan
) -> None:
    started = bench.run(ran(conn, alice, trial(conn, plan, LINES, "crlf")))
    chosen = {plan.named("scorer", name).digest for name in ("lines", "whole")}
    said: list[ScoringEvent] = []
    graded = bench.score(started, chosen, said.append)
    starts = {(e.scorer, e.name, e.score) for e in said if isinstance(e, ScorerStarted)}
    assert starts == {(g.scorer.digest, g.name, scored(g)) for g in graded}

    halt = Halt()
    halt.set()
    before = len(bench.scores_of(started, every=True))
    assert {g.refused for g in bench.score(started, chosen, halt=halt)} == {"stopped"}
    assert len(bench.scores_of(started, every=True)) == before


def test_a_hand_written_configuration_on_another_model_than_its_skeleton_s_says_so(
    bench: Bench, alice: Person
) -> None:
    lines = bench.variation(LINES).configuration
    _ = bench.catalog.create(lines.digest, alice.id, name="by hand")
    variation = bench.variation("by hand")
    assert variation.recipe is None

    def codes(endpoint: str) -> set[str]:
        return {
            f.code
            for f in bench.findings(variation, bench.endpoint(endpoint).engine, 7)
        }

    assert "trial.engine_unmatched" in codes(GPT_OSS)
    assert "trial.engine_unmatched" not in codes(QWEN_BARE)


def test_a_finding_in_each_language_s_trial_is_said_once(bench: Bench) -> None:
    near_greedy, _ = bench.thread("near-greedy", "sampling")
    variation = bench.variation(LINES_GUIDED, {"sampling": near_greedy.digest})
    carried = bench.languages(variation, [f.case for f in bench.families()])
    assert [c.language for c in carried if c.skeleton is not None] == ["en", "sv"]
    found = bench.findings(variation, bench.endpoint(QWEN).engine, 7, carried)
    assert [f.code for f in found].count("vllm.temperature_clamped") == 1
