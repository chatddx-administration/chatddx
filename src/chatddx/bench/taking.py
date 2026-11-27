from collections.abc import Iterable

from chatddx.catalog import About, Edit, Entry, EntryField, Subject, threads
from chatddx.factors.base import resolve
from chatddx.factors.scoring import Expectation
from chatddx.identity import collaborates, owns

from .errors import Conflict, NotFound
from .model import Taken
from .seen import Seen, choices


def take(
    seen: Seen, cases: Iterable[str], schema: str, owner: str | None = None
) -> Taken:
    if seen.rows.kind(schema) != "expectation_schema":
        raise ValueError(f"{schema} isn't a stored expectation schema")
    by = None if owner is None else seen.people.find(owner)
    if owner is not None and by is None:
        raise NotFound(f"no person {owner!r}")
    wanted = list(dict.fromkeys(cases))
    held = threads.expecting(seen.rows, wanted, schema)
    person = seen.person.id
    found = Taken({}, {}, {}, [])
    with seen.conn.transaction():
        for case in wanted:
            offered = [
                (e, a)
                for e, a in held[case]
                if collaborates(person, a) and (by is None or a.owner == by.id)
            ]
            if mine := sorted(e.thread for e, a in held[case] if owns(person, a)):
                found.kept[case] = mine[0]
            elif not offered:
                found.missing.append(case)
            elif len(offered) > 1:
                found.choosing[case] = [e.thread for e, _ in offered]
            else:
                found.taken[case] = _fork(seen, *offered[0])
    return found


def take_from(seen: Seen, thread: int, replace: bool = False) -> int:
    edit, about = seen.thread(thread, "expectation")
    if about.owner == seen.person.id:
        raise ValueError(f"expectation {thread} is yours already")
    held = resolve(seen.store.get, edit.digest, Expectation)
    case, schema = held.case, held.expectation_schema
    mine = sorted(choices(seen, [case], schema)[case])
    if mine and not replace:
        raise Conflict.of(
            "%(login)s has their own expectation of %(case)s under %(schema)s "
            + "already, in thread %(thread)s",
            login=seen.person.login,
            case=seen.title(case),
            schema=seen.title(schema),
            thread=mine[0],
        )
    gone = Entry(field=EntryField.DELETED)
    with seen.conn.transaction():
        for own in mine:
            seen.catalog.note(Subject(thread=own), gone, seen.person.id)
        return _fork(seen, edit, about)


def _fork(seen: Seen, head: Edit, about: About) -> int:
    made = seen.catalog.create(
        head.digest, seen.person.id, forked_from=head.id, name=about.name
    )
    return made.thread
