from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import RedirectResponse

from chatddx import catalog
from chatddx.api import families as api, schemas, threads
from chatddx.api.state import refused
from chatddx.bench import Bench, NotFound
from chatddx.catalog import Subject
from chatddx.catalog.titles import CaseTitle
from chatddx.factors.base import resolve
from chatddx.factors.cases import Case
from chatddx.locale import tr

from .changes import changes
from .pages import BenchDep, page
from .threads import Typed, library_page

router = APIRouter()


@router.get("/cases/{family}")
def case_page(
    request: Request, bench: BenchDep, family: int, version: int | None = None
) -> Response:
    shown = api.family(bench, family)
    bindings = bench.rows.bindings([family])
    at = len(bindings) if version is None else version
    if not 1 <= at <= len(bindings):
        raise NotFound.raw(
            "no version %(at)s of case %(family)s: it has %(versions)s",
            at=at,
            family=family,
            versions=len(bindings),
        )
    bound = bindings[at - 1]
    before = None if at == 1 else bindings[at - 2]
    latest = at == len(bindings)
    mine = shown.owner == bench.person.login
    login = bench.person.login
    cases: Sequence[schemas.FamilyCase | _Earlier] = (
        shown.cases
        if latest
        else [
            _earlier(bench, c) for c, _ in bench.rows.bound_to([bound.vignette], "case")
        ]
    )
    appendices = {a for c in cases for a in c.appendices}
    expected = {
        e.expectation
        for c in shown.cases
        if latest
        for e in c.expectations
        if e.expectation is not None
    }
    return page(
        request,
        "case.html",
        person=bench.person,
        case=shown,
        named=bench.family(family, deleted=True).about.name,
        mine=mine,
        bindings=bindings,
        at=at,
        bound=bound,
        by=bench.login(bound.by),
        changed=None
        if before is None
        else changes(
            before.vignette.model_dump(mode="json"),
            bound.vignette.model_dump(mode="json"),
        ),
        latest=latest,
        cases=cases,
        held={e: _thread_of(bench, e) for e in expected},
        titles={a: bench.title(a) for a in appendices},
        own={t.head.digest for t in threads.threads(bench, "expectation", owner=login)},
        schemas=[
            (t.head.digest, t.name or t.title)
            for t in threads.threads(bench, "expectation_schema")
        ],
        begin=_begin,
    )


def _begin(kind: str, **given: str) -> str:
    return "/library/new?" + urlencode(
        [("kind", kind), *((f"f.{k}", v) for k, v in given.items())]
    )


def _thread_of(bench: Bench, digest: str) -> int | None:
    held = bench.holder(digest)
    return None if held is None else held[0].thread


@dataclass(frozen=True)
class _Earlier:
    case: str
    titled: CaseTitle
    appendices: list[str]
    replacement: str
    stored: bool


def _earlier(bench: Bench, case: str) -> _Earlier:
    held = resolve(bench.store.get, case, Case)
    made, _ = catalog.families.replacement(bench.rows, case)
    return _Earlier(
        case,
        bench.titled_case(case),
        list(held.appendices),
        made,
        bench.rows.kind(made) is not None,
    )


@router.get("/cases/{family}/vignette")
def vignette(request: Request, bench: BenchDep, family: int) -> Response:
    return page(
        request,
        "vignette.html",
        person=bench.person,
        case=api.family(bench, family),
        vignette=api.vignette(bench, family),
    )


@router.post("/cases/{family}/said")
def saying(
    bench: BenchDep,
    family: int,
    name: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    tags: Annotated[str, Form()] = "",
    shared: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = "",
) -> Response:
    with refused(NotFound):
        _ = bench.say(
            Subject(family=family),
            name=name.strip() or None,
            description=description.strip() or None,
            tags=_words(tags),
            collaborators=_words(shared),
            language=language.strip() or None,
        )
    return RedirectResponse(f"/cases/{family}", 303)


def _words(given: str) -> list[str]:
    return sorted({w.strip() for w in given.split(",") if w.strip()})


@router.post("/cases/{family}/delete")
def deleting(bench: BenchDep, family: int) -> Response:
    with refused():
        _ = bench.say(Subject(family=family), deleted=True)
    return RedirectResponse(f"/cases/{family}", 303)


@router.post("/cases/{family}/restore")
def restoring(bench: BenchDep, family: int) -> Response:
    with refused():
        _ = bench.say(Subject(family=family), deleted=False)
    return RedirectResponse(f"/cases/{family}", 303)


@router.post("/cases/{family}/leave")
def leaving(bench: BenchDep, family: int) -> Response:
    _ = api.family(bench, family)
    with refused(NotFound):
        _ = bench.leave(Subject(family=family))
    return RedirectResponse("/library?kind=case", 303)


@router.post("/cases/{family}/replacement")
def replacing(
    bench: BenchDep,
    family: int,
    case: Annotated[str, Form()],
    version: Annotated[int, Form()],
) -> Response:
    with refused(LookupError):
        _ = bench.replacement(case)
    return RedirectResponse(f"/cases/{family}?version={version}", 303)


@router.post("/library/takes")
def taking(
    request: Request,
    bench: BenchDep,
    expectation_schema: Annotated[str, Form()],
    families: Annotated[list[int] | None, Form(alias="family")] = None,
    owner: Annotated[str, Form()] = "",
    tag: Annotated[list[str] | None, Form()] = None,
) -> Response:
    if not families:
        typed = Typed([tr("pick one case or more to take for")], kept=False)
        return library_page(request, bench, "case", tag, typed)
    listed = {f.id: f for f in api.families(bench)}
    if missing := [f for f in families if f not in listed]:
        raise NotFound.raw(
            "no case %(case)s for %(login)s", case=missing[0], login=bench.person.login
        )
    named = {listed[f].case: listed[f].name for f in families}
    with refused(NotFound):
        taken = bench.take(named, expectation_schema, owner.strip() or None)
    return page(
        request,
        "taken.html",
        person=bench.person,
        schema=bench.title(expectation_schema),
        named=named,
        taken=taken,
        owners={
            t: threads.thread(bench, t).owner
            for held in taken.choosing.values()
            for t in held
        },
        back="/library?"
        + urlencode([("kind", "case"), *(("tag", t) for t in sorted(tag or ()))]),
    )
