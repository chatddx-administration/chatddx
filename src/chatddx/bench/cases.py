from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from chatddx import settings
from chatddx.catalog import Entry, EntryField, Subject, families
from chatddx.catalog.read import abouts
from chatddx.factors.base import Fingerprint, Invalid
from chatddx.factors.bundle import Registry
from chatddx.factors.cases import Case, Vignette
from chatddx.identity import sees
from chatddx.inventory import DatabaseSource
from chatddx.store import Texts

from .errors import NotFound, OverQuota
from .model import Family
from .seen import Seen


def case(seen: Seen, family: int, appendices: Sequence[str]) -> str:
    found = seen.family(family)
    for digest in appendices:
        held = seen.rows.edits_holding([digest])
        threads = [Subject(thread=e.thread) for e in held]
        if not any(
            sees(seen.person.id, a) for a in abouts(seen.rows, threads).values()
        ):
            raise NotFound(f"no appendix {digest} for {seen.person.login}")
    made = Case(vignette=found.vignette, appendices=tuple(appendices))
    registry = seen.store.load(appendices)
    _ = seen.store.add(registry, [registry.add(made)])
    return made.digest


def replacement(seen: Seen, case: str) -> str:
    family = families.family_of(seen.rows, case)
    if family is None:
        raise NotFound(f"no case {case} for {seen.person.login}")
    _ = seen.family(family)
    made, registry = families.replacement(seen.rows, case)
    _ = seen.store.add(registry, list(registry))
    return made


def type_case(
    seen: Seen,
    text: str,
    *,
    language: str,
    name: str | None = None,
    source: str | None = None,
) -> Family:
    if not text.strip():
        raise Invalid.raw("a typed case holds text")
    if "\0" in text:
        raise Invalid.of("U+0000 can't be stored")
    if len(text) > settings.TYPED_TEXT_LIMIT:
        raise Invalid.raw(
            "a typed case holds at most %(num)s characters, not %(given)s",
            num=settings.TYPED_TEXT_LIMIT,
            given=len(text),
        )
    if name == "":
        raise Invalid.raw("a name can't be empty: none leaves the case unnamed")
    entries = [Entry(field=EntryField.LANGUAGE, value=language)]
    if name is not None:
        entries.append(Entry(field=EntryField.NAME, value=name))
    try:
        into = seen.inventory.source(source, DatabaseSource).name
    except LookupError as e:
        raise ValueError(str(e)) from None
    texts = Texts(seen.conn)
    since = datetime.now(UTC) - timedelta(days=1)
    if (typed := texts.typed_since(seen.person.id, since)) >= settings.TYPED_PER_DAY:
        raise OverQuota.of(
            "over the day's quota: %(used)s of %(limit)s",
            used=typed + 1,
            limit=settings.TYPED_PER_DAY,
        )
    with seen.conn.transaction():
        id = texts.add(into, text, seen.person.id)
        vignette = Vignette(
            source=into, id=id, fingerprint=Fingerprint.of(text.encode())
        )
        registry = Registry()
        case = registry.add(Case(vignette=vignette))
        _ = seen.store.add(registry, [case])
        family = seen.catalog.adopt(case, seen.person.id, by_content=False)
        for entry in entries:
            seen.catalog.note(Subject(family=family), entry, seen.person.id)
    return seen.family(family)
