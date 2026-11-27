from collections.abc import Callable

import pytest

from chatddx.bench import Bench, NotFound
from chatddx.bench.test.helpers import owned
from chatddx.catalog import About, Subject
from chatddx.identity import Person, sees
from chatddx.store import Rows
from chatddx.test.helpers import TYPED
from chatddx.test.world import LINES


def _mine(bench: Bench) -> int:
    edit, _ = bench.thread(LINES, "configuration")
    return edit.thread


def _entries(bench: Bench, thread: int) -> int:
    return len(Rows(bench.conn).entries([Subject(thread=thread)]))


def test_an_owner_says_what_a_thread_is_called_and_who_it_is_shared_with(
    bench: Bench, bob: Person
) -> None:
    mine = _mine(bench)
    said = bench.say(
        Subject(thread=mine),
        name="terse",
        description="Short answers.",
        tags=["ddx", "short"],
        collaborators=["bob"],
    )
    assert (said.name, said.description) == ("terse", "Short answers.")
    assert (said.tags, said.collaborators) == ({"ddx", "short"}, {bob.id})
    assert sees(bob.id, said)

    written = _entries(bench, mine)
    again = bench.say(
        Subject(thread=mine), name="terse", tags=["short", "ddx"], collaborators=["bob"]
    )
    assert (again, _entries(bench, mine)) == (said, written)

    cleared = bench.say(Subject(thread=mine), name=None, tags=[], collaborators=[])
    assert (cleared.name, cleared.tags, cleared.collaborators) == (None, set(), set())
    assert cleared.description == "Short answers."
    assert not sees(bob.id, cleared)
    assert _entries(bench, mine) == written + 4


def test_only_what_the_owner_may_say_is_said(bench: Bench) -> None:
    mine = _mine(bench)
    archives = bench.thread(f"archive/{LINES}", "configuration")[0].thread
    written = _entries(bench, mine)
    refused: list[tuple[Callable[[], About], type[Exception], str]] = [
        (
            lambda: bench.say(Subject(thread=mine), name=""),
            ValueError,
            "a name can't be empty",
        ),
        (
            lambda: bench.say(Subject(thread=mine), name="kept", tags=["ddx", ""]),
            ValueError,
            "a tag can't be empty",
        ),
        (
            lambda: bench.say(
                Subject(thread=mine), name="kept", collaborators=["nobody"]
            ),
            NotFound,
            "no person 'nobody'",
        ),
        (
            lambda: bench.say(
                Subject(thread=mine), name="kept", collaborators=["alice"]
            ),
            ValueError,
            f"configuration {mine} is yours",
        ),
    ]
    for said, error, message in refused:
        with pytest.raises(error, match=message):
            _ = said()
    assert _entries(bench, mine) == written

    with pytest.raises(NotFound, match=f"no configuration {archives} of yours"):
        _ = bench.say(Subject(thread=archives), name="mine now")
    with pytest.raises(NotFound, match="no thread 999999 of yours"):
        _ = bench.say(Subject(thread=999999), deleted=True)


def test_an_owner_deletes_and_restores_a_thread(bench: Bench) -> None:
    mine = _mine(bench)
    assert bench.say(Subject(thread=mine), deleted=True).deleted
    assert mine not in [e.thread for e, _ in bench.threads("configuration")]
    deleted = bench.threads("configuration", deleted=True)
    assert [e.thread for e, _ in deleted] == [mine]
    with pytest.raises(NotFound, match=f"no configuration {mine} for alice"):
        _ = bench.thread(mine, "configuration")
    _, about = bench.thread(mine, "configuration", deleted=True)
    assert about.deleted

    with pytest.raises(ValueError, match="is deleted: restore it to say more of it"):
        _ = bench.say(Subject(thread=mine), name="gone")
    back = bench.say(Subject(thread=mine), deleted=False, name="back")
    assert (back.deleted, back.name) == (False, "back")
    assert bench.threads("configuration", deleted=True) == []


def test_a_restore_is_held_to_one_expectation_per_case_and_schema(
    bench: Bench,
) -> None:
    case = bench.family("noted").case
    [schema] = bench.expectation_schemas(case)
    [mine] = owned(bench, case, schema)
    [(archives, _)] = bench.shared(case, schema)
    _ = bench.say(Subject(thread=mine), deleted=True)
    taken = bench.take_from(archives.thread)

    with pytest.raises(ValueError, match=f"already, in thread {taken}"):
        _ = bench.say(Subject(thread=mine), deleted=False)
    _ = bench.say(Subject(thread=taken), deleted=True)
    assert not bench.say(Subject(thread=mine), deleted=False).deleted


def test_a_description_is_taken_away_as_a_name_is(bench: Bench) -> None:
    mine = _mine(bench)
    assert bench.say(Subject(thread=mine), description=None).description is None
    written = _entries(bench, mine)
    assert bench.say(Subject(thread=mine), description=None).description is None
    assert _entries(bench, mine) == written

    _ = bench.say(Subject(thread=mine), description="Short answers.")
    with pytest.raises(ValueError, match="a description can't be empty: none takes"):
        _ = bench.say(Subject(thread=mine), description="")
    assert bench.say(Subject(thread=mine), name="kept").description == "Short answers."
    assert bench.say(Subject(thread=mine), description=None).description is None
    assert _entries(bench, mine) == written + 3


def test_a_collaborator_leaves_a_share_until_it_is_shared_again(
    bench: Bench, bob: Person
) -> None:
    mine = _mine(bench)
    _ = bench.say(Subject(thread=mine), collaborators=["bob"])
    bobs = Bench(bench.conn, bob, bench.inventory)
    with pytest.raises(NotFound, match=f"no configuration {mine} shared with alice"):
        _ = bench.leave(Subject(thread=mine))

    left = bobs.leave(Subject(thread=mine))
    assert (left.owner, left.collaborators) == (bench.person.id, set())
    assert mine not in [e.thread for e, _ in bobs.threads("configuration")]
    with pytest.raises(NotFound, match=f"no configuration {mine} shared with bob"):
        _ = bobs.leave(Subject(thread=mine))

    assert sees(bob.id, bench.say(Subject(thread=mine), collaborators=["bob"]))


def test_an_owner_corrects_a_case_s_language_and_deletes_it(bench: Bench) -> None:
    typed = bench.type_case(TYPED, name="flight", language="en").id
    case = Subject(family=typed)
    said = bench.say(case, name="breathless", language="sv")
    assert (said.name, said.language) == ("breathless", "sv")
    assert bench.say(case, language="sv") == said
    with pytest.raises(ValueError):
        _ = bench.say(case, language="Swedish")
    with pytest.raises(ValueError, match="a language entry is for a family's vignette"):
        _ = bench.say(Subject(thread=_mine(bench)), language="sv")

    assert bench.say(case, deleted=True).deleted
    assert typed not in [f.id for f in bench.families()]
    assert [f.id for f in bench.families(deleted=True)] == [typed]
    with pytest.raises(NotFound, match=f"no case {typed} for alice"):
        _ = bench.family(typed)
    assert bench.family(typed, deleted=True).about.deleted
    with pytest.raises(ValueError, match=f"case {typed} is deleted: restore it"):
        _ = bench.say(case, name="gone")


def test_a_collaborator_says_a_case_s_tags_and_language_alone_and_leaves_it(
    bench: Bench,
) -> None:
    shared = bench.family("crlf")
    assert shared.about.owner != bench.person.id
    subject = Subject(family=shared.id)
    said = bench.say(subject, tags=[*shared.about.tags, "reviewed"], language="sv")
    assert "reviewed" in said.tags and said.language == "sv"
    assert said.owner == shared.about.owner
    refused: list[Callable[[], About]] = [
        lambda: bench.say(subject, name="mine now"),
        lambda: bench.say(subject, description="Mine."),
        lambda: bench.say(subject, collaborators=["bob"]),
        lambda: bench.say(subject, deleted=True),
        lambda: bench.say(subject, tags=["reviewed"], name="mine now"),
    ]
    for said_more in refused:
        with pytest.raises(NotFound, match=f"no case {shared.id} of yours"):
            _ = said_more()
    left = bench.leave(Subject(family=shared.id))
    assert not sees(bench.person.id, left)
    assert shared.id not in [f.id for f in bench.families()]
    with pytest.raises(NotFound, match=f"no case {shared.id} shared with alice"):
        _ = bench.leave(Subject(family=shared.id))
    with pytest.raises(NotFound, match="no case 999999 of yours"):
        _ = bench.say(Subject(family=999999), name="nowhere")
