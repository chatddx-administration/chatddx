import pytest

from chatddx.catalog import Entry, EntryField, Subject, threads
from chatddx.catalog.test.memory import Memory, compiled
from chatddx.factors.bundle import Registry
from chatddx.factors.request import Instructions, Sampling
from chatddx.factors.test.sample import generation_recipe, world


def test_heads_say_what_is_deleted_and_names_skip_it() -> None:
    reg = Registry()
    ids = world(reg)
    rows = Memory(reg)
    kept, dropped = rows.start(ids["trial"]), rows.start(ids["trial"])
    for edit in (kept, dropped):
        rows.note(
            Subject(thread=edit.thread), Entry(field=EntryField.NAME, value="baseline")
        )
    rows.note(Subject(thread=dropped.thread), Entry(field=EntryField.DELETED))
    assert [(e, a.deleted) for e, a in threads.heads(rows, "trial")] == [
        (kept, False),
        (dropped, True),
    ]
    assert threads.find(rows, "trial", "baseline") == [kept.thread]
    with pytest.raises(LookupError):
        _ = threads.history(rows, 99)


def test_forks_vary_their_base_and_follow_it_on_request() -> None:
    reg = Registry()
    rows = Memory(reg)
    recommended, longer, cooler, cooler_longer = (
        reg.add(Sampling(temperature=0.6, top_p=0.95)),
        reg.add(Sampling(temperature=0.6, top_p=0.95, max_output_tokens=4096)),
        reg.add(Sampling(temperature=0.7, top_p=0.95)),
        reg.add(Sampling(temperature=0.7, top_p=0.95, max_output_tokens=4096)),
    )
    origin = rows.start(recommended)
    fork = rows.start(longer, forked_from=origin.id)
    assert threads.forks(rows, origin.thread) == [fork.thread]
    assert (threads.origin(rows, fork.thread), threads.origin(rows, origin.thread)) == (
        origin.thread,
        None,
    )
    diverged = threads.divergence(rows, fork.thread)
    assert diverged is not None
    assert (diverged.varies, diverged.moved) == (
        {"/max_output_tokens": (None, 4096)},
        False,
    )
    assert threads.proposal(rows, fork.thread) is None

    moved = rows.save(origin.thread, cooler)
    assert threads.proposal(rows, fork.thread) == reg.get(cooler_longer)
    threads.check_edit(rows, fork.thread, cooler_longer, based_on=moved.id)
    with pytest.raises(ValueError, match="origin"):
        threads.check_edit(rows, fork.thread, cooler_longer, based_on=fork.id)
    _ = rows.save(fork.thread, cooler_longer, based_on=moved.id)
    diverged = threads.divergence(rows, fork.thread)
    assert diverged is not None
    assert (diverged.base, diverged.moved) == (moved, False)


def test_behind_names_every_thread_that_moved_on() -> None:
    reg = Registry()
    rows = Memory(reg)
    recipe = generation_recipe(reg)
    plan = compiled(reg, recipe)
    assert recipe.instructions is not None
    shared = rows.start(recipe.instructions)
    forked = rows.start(recipe.instructions, forked_from=shared.id)
    skeleton = rows.start(plan.skeleton, compilation=plan.digest)
    assert threads.behind(rows, skeleton.thread) == []

    one = rows.save(
        shared.thread, reg.add(Instructions(text="You are a cardiologist."))
    )
    two = rows.save(forked.thread, reg.add(Instructions(text="You are a surgeon.")))
    assert [(b.path, b.head) for b in threads.behind(rows, skeleton.thread)] == [
        ("/recipe/instructions", one),
        ("/recipe/instructions", two),
    ]
    rows.note(Subject(thread=forked.thread), Entry(field=EntryField.DELETED))
    assert [b.head for b in threads.behind(rows, skeleton.thread)] == [one]


def test_an_earlier_version_brought_back_is_that_version_again() -> None:
    reg = Registry()
    rows = Memory(reg)
    cool, warm = reg.add(Sampling(temperature=0.6)), reg.add(Sampling(temperature=0.9))
    first = rows.start(cool)
    second = rows.save(first.thread, warm)
    back = rows.save(first.thread, cool)
    later = rows.save(first.thread, reg.add(Sampling(temperature=0.7)))
    assert threads.versions(rows, first.thread) == {
        first.id: 1,
        second.id: 2,
        back.id: 1,
        later.id: 3,
    }
