from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlencode

from fastapi import APIRouter, Form, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import JsonValue

from chatddx.api import (
    families as api_families,
    schemas,
    threads as api,
)
from chatddx.api.standing import against, configurations as owned, standing
from chatddx.api.state import refused
from chatddx.bench import Bench, Family, NotFound
from chatddx.catalog import Edit, Subject, read
from chatddx.factors.base import Fingerprint, Invalid, resolve
from chatddx.factors.cases import Appendix, Case, Vignette
from chatddx.factors.gathering import REVIEW
from chatddx.factors.request import Translations
from chatddx.factors.scoring import Expectation, ExpectationSchema, Scorer
from chatddx.factors.select import field
from chatddx.locale import display_language
from chatddx.store import Queue, fetch_vignette

from .mending import mend, placed
from .pages import BenchDep, configurations, page, within
from .titles import display_case

router = APIRouter()

type Tags = Annotated[list[str] | None, Query()]


@router.get("/review")
def reviewing(
    request: Request, bench: BenchDep, tag: Tags = None, language: Tags = None
) -> Response:
    listed = _listed(api_families.families(bench), tag, language)
    if listed:
        kept = _query(tag=tag, language=language)
        return RedirectResponse(f"/review/{listed[0].id}{kept}", 303)
    return page(request, "review.html", person=bench.person, family=None, tag=tag)


@router.get("/review/{family}")
def review(
    request: Request,
    bench: BenchDep,
    family: int,
    case: str | None = None,
    schema: str | None = None,
    measure: str | None = None,
    tag: Tags = None,
    language: Tags = None,
) -> Response:
    shown = api_families.family(bench, family)
    picked = _picked(shown, case)
    visible = _schemas(bench)
    under = _under(visible, schema)
    expected = next(
        (e for e in picked.expectations if e.expectation_schema == under), None
    )
    every = api_families.families(bench)
    listed = _listed(every, tag, language)
    keep = {"tag": tag, "language": language, "schema": schema}
    own = _own(bench, expected)
    offered = (
        []
        if expected is None or expected.expectation is not None
        else [
            (t, resolve(bench.store.get, t.head.digest, Expectation).data)
            for t in expected.shared
        ]
    )
    seen = _seen(bench)
    appendices = _appendices(bench, picked.appendices, seen)
    branch = _branches(bench, bench.family(family), seen).get(picked.case)
    last = None if branch is None else seen[branch.appendices[-1]]
    live = configurations(bench)
    busy = _busy(bench, picked.case)
    editor = _editing(bench, shown, picked, under, expected, own)
    measurable = [] if editor is None else _measurable(bench, under)
    measuring = measure if measure in measurable else None
    query = request.url.query
    back = request.url.path + (f"?{query}" if query else "")
    props: dict[str, Any] = {
        "family": family,
        "case": picked.case,
        "expected": {
            "editor": editor,
            "history": [] if own is None else _history(bench, own),
        },
        "appendices": appendices,
        "back": back,
        "schema": under,
        "measure": {"fields": measurable, "field": measuring},
        "about": {
            "family": family,
            "tags": shown.tags,
            "language": shown.language,
            "languages": _languages(bench, every, shown.language),
            "editable": bench.person.login in [shown.owner, *shown.collaborators],
        },
    }
    return page(
        request,
        "review.html",
        person=bench.person,
        family=shown,
        every=every,
        listed={f.id for f in listed},
        marks=_marks(bench, every, seen),
        tags=sorted({t for f in every for t in f.tags}),
        languages=sorted({f.language for f in every if f.language}),
        tag=tag,
        keep=keep,
        toggled=_toggled,
        case=picked,
        appendices=appendices,
        deleting=None
        if last is None or last.owner != bench.person.login
        else last.name or last.title,
        visible=visible,
        schema=under,
        expected=expected,
        own=own,
        offered=offered,
        carried=_carried(bench, shown, picked, under, expected),
        runnable=sum(placed(bench, t) is not None for t in live),
        busy=busy,
        measuring=measuring,
        back=back,
        props=props,
        query=_query,
        island="review",
    )


@router.post("/review/{family}/runs")
def running_in_review(
    bench: BenchDep,
    family: int,
    case: Annotated[str, Form()],
    under: Annotated[str | None, Form()] = None,
    back: Annotated[str | None, Form()] = None,
) -> Response:
    picked = _picked(api_families.family(bench, family), case)
    # Policy: as on the run page, a press made while a run of the case is under way
    # counts as made.
    if _busy(bench, picked.case):
        return _moved(family, back, picked.case)
    schema = _under(_schemas(bench), under)
    expected = next(
        (e for e in picked.expectations if e.expectation_schema == schema), None
    )
    marked = expected is not None and expected.expectation is not None
    left = against(bench, schema, marked)
    stood = standing(bench, owned(bench), [picked.case], REVIEW, left)
    if not mend(bench, stood, [picked.case], REVIEW, left):
        raise Invalid.of(
            "no configuration can run %(case)s now", case=display_case(picked.titled)
        )
    return _moved(family, back, picked.case)


def _schemas(bench: Bench) -> list[schemas.Thread]:
    found = api.threads(bench, "expectation_schema")
    return sorted(found, key=lambda t: t.name or t.title)


def _under(visible: list[schemas.Thread], schema: str | None) -> str | None:
    under = next(
        (t.head.digest for t in visible if schema in (None, t.head.digest)), None
    )
    if schema is not None and under is None:
        raise NotFound.raw("no expectation schema %(schema)s for you", schema=schema)
    return under


_OPEN_STATUSES = ("queued", "under way")


def _busy(bench: Bench, case: str) -> bool:
    placed = Queue(bench.conn).placed([r.run for r in bench.runs(reaching=case)])
    return any(p.job.status in _OPEN_STATUSES for p in placed.values())


@router.post("/review/{family}/delete")
def deleting_in_review(
    bench: BenchDep,
    family: int,
    case: Annotated[str, Form()],
    back: Annotated[str | None, Form()] = None,
) -> Response:
    shown = bench.family(family)
    seen = _seen(bench)
    branch = _branches(bench, shown, seen).get(case)
    if branch is None:
        raise NotFound.raw(
            "no appendix to delete in case %(case)s of %(family)s",
            case=case,
            family=shown.name,
        )
    with refused():
        _ = bench.say(Subject(thread=seen[branch.appendices[-1]].id), deleted=True)
    return _moved(family, back, branch.parent)


type _Given = str | int | list[str] | None


def _query(**given: _Given) -> str:
    pairs: list[tuple[str, str | int]] = [
        (k, v)
        for k, held in given.items()
        for v in (held if isinstance(held, list) else [held])
        if v is not None
    ]
    return "?" + urlencode(pairs) if pairs else ""


def _picked(shown: schemas.FamilyDetail, case: str | None) -> schemas.FamilyCase:
    picked = next((c for c in shown.cases if case in (None, c.case)), None)
    if picked is None:
        raise NotFound.raw(
            "no case %(case)s of %(family)s", case=str(case), family=shown.name
        )
    return picked


def _moved(family: int, back: str | None, case: str) -> RedirectResponse:
    path, _, query = within(back or f"/review/{family}").partition("?")
    kept = [(k, v) for k, v in parse_qsl(query) if k not in ("case", "evaluation")]
    said = urlencode([*kept, ("case", case)])
    return RedirectResponse(f"{path}?{said}", 303)


def _listed(
    every: list[schemas.Family], tag: list[str] | None, language: list[str] | None
) -> list[schemas.Family]:
    return [
        f
        for f in every
        if set(tag or ()) <= set(f.tags) and (not language or f.language in language)
    ]


def _toggled(picked: list[str] | None, value: str) -> list[str]:
    held = [p for p in picked or () if p != value]
    return held if value in (picked or ()) else [*held, value]


def _languages(
    bench: Bench, every: list[schemas.Family], current: str | None
) -> list[tuple[str, str]]:
    found = {f.language for f in every if f.language}
    found |= {t.language for t in api.threads(bench, "configuration") if t.language}
    for t in api.threads(bench, "translations"):
        found |= set(resolve(bench.store.get, t.head.digest, Translations).into)
    found |= {current} if current else set()
    return sorted(((t, display_language(t)) for t in found), key=lambda t: t[1])


def _seen(bench: Bench) -> dict[str, schemas.Thread]:
    login = bench.person.login
    held = sorted(api.threads(bench, "appendix"), key=lambda t: t.owner == login)
    return {t.head.digest: t for t in held}


@dataclass(frozen=True)
class _Branch:
    appendices: tuple[str, ...]
    parent: str


def _branches(
    bench: Bench, family: Family, seen: dict[str, schemas.Thread]
) -> dict[str, _Branch]:
    built: dict[tuple[str, ...], str] = {}
    for c in family.cases:
        appendices = resolve(bench.store.get, c, Case).appendices
        if c != family.case and appendices and all(a in seen for a in appendices):
            built[appendices] = c
    return {
        c: _Branch(
            appendices,
            next(
                (
                    built[appendices[:n]]
                    for n in range(len(appendices) - 1, 0, -1)
                    if appendices[:n] in built
                ),
                family.case,
            ),
        )
        for appendices, c in built.items()
    }


def _grown(
    branches: dict[str, _Branch], under: str, seen: dict[str, schemas.Thread]
) -> list[dict[str, Any]]:
    start = len(branches[under].appendices) if under in branches else 0
    found = [
        {
            "case": c,
            "names": [seen[a].name or seen[a].title for a in b.appendices[start:]],
            "branches": _grown(branches, c, seen),
        }
        for c, b in branches.items()
        if b.parent == under
    ]
    return sorted(found, key=lambda b: b["names"])


def _marks(
    bench: Bench, every: list[schemas.Family], seen: dict[str, schemas.Thread]
) -> dict[int, dict[str, Any]]:
    held = {f.id: f for f in bench.families()}
    found: dict[int, dict[str, Any]] = {}
    for f in every:
        family = held[f.id]
        branches = _branches(bench, family, seen)
        found[f.id] = {
            "drifted": _drifted(bench, family.vignette),
            "branches": _grown(branches, family.case, seen),
            "cases": {family.case, *branches},
        }
    return found


def _drifted(bench: Bench, vignette: Vignette) -> bool | None:
    if vignette.fingerprint.key_id is not None:
        return None
    try:
        raw = fetch_vignette(bench.conn, bench.inventory, vignette)
    except LookupError:
        return True
    return Fingerprint.of(raw) != vignette.fingerprint


def _appendices(
    bench: Bench, digests: list[str], seen: dict[str, schemas.Thread]
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for d in digests:
        held = resolve(bench.store.get, d, Appendix)
        t = seen.get(d)
        mine = None if t is None or t.owner != bench.person.login else t
        found.append(
            {
                "digest": d,
                "title": bench.title(d),
                "text": held.text,
                "vignette": held.vignette.model_dump(mode="json"),
                "thread": None if mine is None else mine.id,
                "head": None if mine is None else mine.head.id,
            }
        )
    return found


def _mine(bench: Bench, digests: list[str]) -> dict[str, Edit]:
    held = read.heads_holding(bench.rows, digests)
    abouts = read.abouts(bench.rows, [Subject(thread=t) for t in held])
    return {
        e.digest: e
        for t, e in held.items()
        if (a := abouts[Subject(thread=t)]).owner == bench.person.id and not a.deleted
    }


def _measurable(bench: Bench, schema: str | None) -> list[str]:
    if schema is None:
        return []
    read: set[str] = set()
    for t in api.threads(bench, "scorer"):
        held = resolve(bench.store.get, t.head.digest, Scorer)
        if held.expectation_schema == schema:
            read |= {
                f
                for v in held.views
                if v.judge is None and (f := field(v.expectation)) is not None
            }
    held = resolve(bench.store.get, schema, ExpectationSchema).json_schema
    properties = held.get("properties")
    return [f for f in properties if f in read] if isinstance(properties, dict) else []


def _own(bench: Bench, expected: schemas.Expected | None) -> Edit | None:
    if expected is None or expected.expectation is None:
        return None
    return _mine(bench, [expected.expectation]).get(expected.expectation)


def _editing(
    bench: Bench,
    shown: schemas.FamilyDetail,
    picked: schemas.FamilyCase,
    schema: str | None,
    expected: schemas.Expected | None,
    own: Edit | None,
) -> dict[str, Any] | None:
    if schema is None or (expected is not None and expected.ambiguous):
        return None
    given: dict[str, Any] = {
        "kind": "expectation",
        "me": bench.person.login,
        "case": picked.case,
        "schema": schema,
        "json_schema": resolve(bench.store.get, schema, ExpectationSchema).json_schema,
    }
    if own is not None and expected is not None:
        return {
            **given,
            "mode": "edit",
            "thread": own.thread,
            "head": own.id,
            "data": expected.data,
        }
    return {
        **given,
        "mode": "new",
        "data": _started(shown, picked, schema),
    }


def _started(
    shown: schemas.FamilyDetail, picked: schemas.FamilyCase, schema: str
) -> JsonValue:
    if picked.default:
        return None
    return next(
        (
            e.data
            for c in shown.cases
            if c.default
            for e in c.expectations
            if e.expectation_schema == schema and e.expectation is not None
        ),
        None,
    )


def _history(bench: Bench, own: Edit) -> list[dict[str, Any]]:
    return [
        {
            "at": e.at.isoformat(),
            "by": e.by,
            "digest": e.digest,
            "data": resolve(bench.store.get, e.digest, Expectation).data,
        }
        for e in api.edits(bench, own.thread)
    ]


def _carried(
    bench: Bench,
    shown: schemas.FamilyDetail,
    picked: schemas.FamilyCase,
    schema: str | None,
    expected: schemas.Expected | None,
) -> list[tuple[str, Edit]]:
    if schema is None or (
        expected is not None and (expected.expectation or expected.ambiguous)
    ):
        return []
    elsewhere = [
        (c.title, e.expectation)
        for c in shown.cases
        if c.case != picked.case and not c.default
        for e in c.expectations
        if e.expectation_schema == schema and e.expectation is not None
    ]
    own = _mine(bench, [d for _, d in elsewhere])
    return [(title, own[d]) for title, d in elsewhere if d in own]
