from typing import Any

import pytest

from chatddx.bench import Bench, MovedOn, NotFound
from chatddx.bench.test.helpers import component, owned
from chatddx.catalog import Entry, EntryField, Subject, threads
from chatddx.catalog.language import language_of
from chatddx.factors.request import Recipe
from chatddx.factors.scoring import Expectation, Judge
from chatddx.identity import Person
from chatddx.store import Catalog
from chatddx.test.helpers import ZERO
from chatddx.test.world import (
    CLINICIAN,
    GPT_OSS,
    JUDGE,
    LINES,
    MISTRAL,
    MISTRAL_MODEL,
    QWEN,
    QWEN_MODEL,
)


def _archive_s(bench: Bench, word: str) -> tuple[int, dict[str, Any]]:
    text = word == "instructions"
    edit, _ = next(
        (e, a)
        for e, a in bench.threads(word)
        if bench.login(a.owner) == "archive"
        and (not text or language_of(bench.rows, e.digest) is not None)
    )
    return edit.thread, bench.store.get(edit.digest).model_dump(mode="json")


def test_a_person_writes_a_chunk_as_a_thread_of_their_own(bench: Bench) -> None:
    rows = bench.rows
    _, doc = _archive_s(bench, "instructions")
    mine = component({**doc, "text": "You are a careful physician."})

    made = bench.new(mine, "careful", "en")
    assert (made.what, made.findings) == ("created", [])
    thread = made.edit.thread
    about = bench.thread(thread)[1]
    assert (about.name, about.owner) == ("careful", bench.person.id)
    assert threads.thread(rows, thread).forked_from is None
    assert language_of(rows, mine.digest) == "en"

    terse = component({**doc, "text": "Be terse.", "v": 1})
    edited = bench.edit(thread, made.edit.id, terse)
    assert edited.what == "a new version"
    assert language_of(rows, terse.digest) is None
    assert bench.edit(thread, edited.edit.id, terse).what == "unchanged"
    with pytest.raises(MovedOn, match=f"since edit {made.edit.id}"):
        _ = bench.edit(thread, made.edit.id, mine)
    assert [e.digest for e in threads.history(rows, thread)] == [
        mine.digest,
        terse.digest,
    ]


def test_a_person_forks_a_chunk_they_see_as_it_is_or_changed(bench: Bench) -> None:
    rows = bench.rows
    origin, doc = _archive_s(bench, "instructions")
    head = threads.head(rows, origin)
    held = language_of(rows, head.digest)
    assert held is not None

    same = bench.fork(origin, "as is", language=held)
    assert threads.thread(rows, same.edit.thread).forked_from == head.id
    assert same.edit.digest == head.digest
    with pytest.raises(ValueError, match=f"is in {held} already"):
        _ = bench.fork(origin, "relabelled", language="xx")

    changed = component({**doc, "text": "Think it through."})
    fork = bench.fork(origin, "changed", changed, "sv")
    assert fork.edit.digest == changed.digest
    assert language_of(rows, changed.digest) == "sv"
    assert threads.history(rows, origin) == [head]


def test_a_write_is_refused_what_isn_t_the_person_s_to_write(
    bench: Bench, bob: Person
) -> None:
    origin, doc = _archive_s(bench, "instructions")
    _, sampling = _archive_s(bench, "sampling")
    head = threads.head(bench.rows, origin).id
    mine = component({**doc, "text": "Mine."})

    with pytest.raises(NotFound, match=f"no instructions {origin} of yours"):
        _ = bench.edit(origin, head, mine)
    with pytest.raises(ValueError, match="holds chunk.instructions components, not"):
        _ = bench.fork(origin, "odd", component(sampling))
    with pytest.raises(ValueError, match="a person doesn't write tool components"):
        _ = bench.new(bench.store.get(bench.threads("tool")[0][0].digest), "mine")
    with pytest.raises(ValueError, match="chunk.sampling components have no language"):
        _ = bench.new(component(sampling), "cool", "en")
    with pytest.raises(ValueError, match=f"not in the store: \\['{ZERO}'\\]"):
        _ = bench.new(component({"kind": "chunk.toolset", "tools": [ZERO]}), "x")

    theirs = Catalog(bench.conn).create(component(sampling).digest, bob.id)
    with pytest.raises(NotFound, match=f"no sampling {theirs.thread} for alice"):
        _ = bench.fork(theirs.thread, "taken")


@pytest.mark.slow
def test_a_person_writes_expectations_and_hears_what_the_lints_say(
    bench: Bench,
) -> None:
    catalog = bench.catalog
    rows = bench.rows
    case = bench.family("noted").case
    [schema] = bench.expectation_schemas(case)
    [mine] = owned(bench, case, schema)
    head = threads.head(rows, mine)
    odd = Expectation(
        case=case, expectation_schema=schema, data=["not", "an", "object"]
    )

    with pytest.raises(ValueError, match=f"already, in thread {mine}"):
        _ = bench.new(odd, "second")
    with pytest.raises(ValueError, match="expectation components have no language"):
        _ = bench.edit(mine, head.id, odd, "en")
    edited = bench.edit(mine, head.id, odd)
    assert edited.what == "a new version"
    assert [f.code for f in edited.findings] == ["expectation.invalid"]
    assert bench.expectation(case, schema) == odd

    [archives] = [
        e.thread
        for e, a in threads.expecting(rows, [case])[case]
        if bench.login(a.owner) == "archive"
    ]
    with pytest.raises(ValueError, match="has their own expectation of"):
        _ = bench.fork(archives, "theirs")
    catalog.note(Subject(thread=mine), Entry(field=EntryField.DELETED), bench.person.id)
    fork = bench.fork(archives, "theirs, mended", odd)
    assert (
        threads.thread(rows, fork.edit.thread).forked_from
        == threads.head(rows, archives).id
    )
    assert bench.expectation(case, schema) == odd


def test_a_recipe_of_the_person_s_making_is_compiled_into_a_configuration(
    bench: Bench,
) -> None:
    engine = bench.endpoint(QWEN).engine
    rows = bench.rows
    recipe = Recipe(
        instructions=bench.thread(CLINICIAN, "instructions")[0].digest,
        few_shot=bench.thread("worked-example", "few_shot")[0].digest,
        prompt=bench.thread("case", "prompt")[0].digest,
        output=bench.thread("lines", "output")[0].digest,
        sampling=bench.thread("greedy", "sampling")[0].digest,
        reasoning=bench.thread("off", "reasoning")[0].digest,
        model=bench.endpoint(QWEN).model.digest,
    )

    made = bench.new(recipe, "my own")
    assert (made.what, made.findings) == ("created", [])
    thread = made.edit.thread
    assert threads.thread(rows, thread).forked_from is None
    assert threads.recipe(rows, threads.head(rows, thread)) == recipe
    assert made.edit.compilation is not None
    assert language_of(rows, made.edit.digest) == "en"
    found = bench.variation("my own")
    assert found.configuration == made.edit
    messages = bench.request(found, engine, 7)["messages"]
    assert isinstance(messages, list) and len(messages) == 4


def test_a_recipe_is_refused_what_doesn_t_compile(bench: Bench) -> None:
    prompt = bench.thread("case", "prompt")[0].digest
    output = bench.thread("lines", "output")[0].digest
    sampling = bench.thread("greedy", "sampling")[0].digest
    model = bench.endpoint(QWEN).model.digest
    recipe = Recipe(prompt=prompt, output=output, sampling=sampling, model=model)

    with pytest.raises(ValueError, match=f"{output} isn't a stored chunk of prompt"):
        _ = bench.new(recipe.model_copy(update={"prompt": output}), "x")
    with pytest.raises(ValueError, match=f"{output} isn't a stored model"):
        _ = bench.new(recipe.model_copy(update={"model": output}), "x")
    on = recipe.model_copy(
        update={
            "reasoning": bench.thread("on", "reasoning")[0].digest,
            "model": bench.endpoint(MISTRAL).model.digest,
        }
    )
    with pytest.raises(ValueError, match=f"{MISTRAL_MODEL}: .*doesn't reason"):
        _ = bench.new(on, "x")
    with pytest.raises(ValueError, match=f"{ZERO} isn't a stored chunk of toolset"):
        _ = bench.new(recipe.model_copy(update={"toolset": ZERO}), "x")
    with pytest.raises(ValueError, match="language comes from its recipe"):
        _ = bench.new(recipe, "x", "en")
    with pytest.raises(ValueError, match="generation prompt in a judge recipe"):
        _ = bench.new(recipe.model_copy(update={"purpose": "judge"}), "x")


def test_a_person_writes_a_judge_over_a_judge_configuration(bench: Bench) -> None:
    skeleton = bench.variation(JUDGE).configuration.digest
    weights = bench.endpoint(QWEN).model.digest
    written = bench.new(Judge(skeleton=skeleton, model=weights, seeds=(1, 2)), "twice")
    assert written.what == "created"
    assert [f.code for f in written.findings] == ["judge.greedy_seeds"]

    thread, _ = _archive_s(bench, JUDGE)
    forked = bench.fork(thread, "mine")
    assert (
        forked.what == "created"
        and bench.thread(forked.edit.thread)[1].owner == bench.person.id
    )
    once = Judge(skeleton=skeleton, model=weights, seeds=(3,))
    edited = bench.edit(forked.edit.thread, forked.edit.id, once)
    assert (edited.what, edited.edit.digest) == ("a new version", once.digest)

    generation = bench.variation(LINES).configuration.digest
    with pytest.raises(ValueError, match="judge uses a generation skeleton"):
        _ = bench.new(Judge(skeleton=generation, model=weights, seeds=(1,)), "wrong")


def test_a_judge_on_another_model_than_its_skeleton_is_worked_out_for_says_so(
    bench: Bench,
) -> None:
    graded = bench.variation("judge-graded").configuration.digest
    gpt_oss = bench.endpoint(GPT_OSS).model.digest
    judge = Judge(skeleton=graded, model=gpt_oss, seeds=(1,))
    said = f"the skeleton is worked out for {QWEN_MODEL}, but the judge's model is "
    for findings in (
        bench.check(judge).findings,
        bench.new(judge, "elsewhere").findings,
    ):
        [unmatched] = [f for f in findings if f.code == "judge.model_unmatched"]
        assert unmatched.message.startswith(said)
    qwen = bench.endpoint(QWEN).model.digest
    on_qwen = Judge(skeleton=graded, model=qwen, seeds=(1,))
    assert "judge.model_unmatched" not in {
        f.code for f in bench.check(on_qwen).findings
    }
    greedy = bench.variation(JUDGE).configuration.digest
    anywhere = Judge(skeleton=greedy, model=gpt_oss, seeds=(1,))
    assert "judge.model_unmatched" not in {
        f.code for f in bench.check(anywhere).findings
    }
