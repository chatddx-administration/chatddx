import json
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Annotated, Any, Literal, cast
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, JsonValue, ValidationError
from starlette.datastructures import FormData

from chatddx import catalog
from chatddx.api import families, schemas, threads as api
from chatddx.api.state import Refusing, refused
from chatddx.bench import KINDS, WRITTEN, Bench, NotFound, Titled, word_of
from chatddx.bench.seen import compiled
from chatddx.catalog import LANGUAGE_KINDS, Labels, Subject, read
from chatddx.factors.base import Component, Invalid, language_tag, resolve
from chatddx.factors.kinds import BY_KIND
from chatddx.factors.request import RECIPE_PARTS, Purpose, Recipe, Translations
from chatddx.factors.scoring import Expectation, Scorer
from chatddx.factors.trial import Trial, suggest_seeds
from chatddx.identity import sees
from chatddx.ledger import RunStarted
from chatddx.locale import pgettext, pgettext_noop

from .changes import changes
from .editors import editors
from .fields import Field, choices, fields, fresh, kept, listed, parsed, purpose
from .pages import BenchDep, own_first, page, refusable, refusal_of, within
from .scoring import checked, code_of, unshipped
from .shelves import AUTHORED, IN_REVIEW, IN_WORLD, SHELVES, display_kind, shelved
from .translations import begun, posted, translating, written as translated

_BEGUN = [w for w in KINDS if set(KINDS[w]) & AUTHORED and w not in IN_REVIEW]

_PURPOSES: dict[Purpose, str] = {
    "generation": pgettext_noop("purpose", "generation"),
    "judge": pgettext_noop("purpose", "judge"),
}

router = APIRouter()


async def _form(request: Request) -> FormData:
    return await request.form()


FormDep = Annotated[FormData, Depends(_form)]


@dataclass(frozen=True)
class Typed:
    refused: list[str]
    name: str | None = None
    language: str | None = None
    labels: str | None = None
    about: dict[str, str] | None = None
    kept: bool = True


@router.get("/library")
def library(
    request: Request,
    bench: BenchDep,
    kind: str | None = None,
    tag: Annotated[list[str] | None, Query()] = None,
    q: str = "",
    pick: Literal["all"] | None = None,
    schema: str | None = None,
) -> Response:
    return library_page(request, bench, kind, tag, q=q, pick=pick, schema=schema)


def _behind(bench: Bench) -> tuple[int, int]:
    found = bench.behind_own()
    heads = catalog.read.heads_of(bench.rows, found)
    kinds = {t: catalog.threads.thread(bench.rows, t).kind for t in found}
    return len(found), sum(bench.outdated(heads[t], kinds[t]) for t in found)


def library_page(
    request: Request,
    bench: Bench,
    kind: str | None,
    tag: list[str] | None,
    typed: Typed | None = None,
    q: str = "",
    pick: Literal["all"] | None = None,
    schema: str | None = None,
) -> Response:
    words = [w for s in SHELVES for w in s.kinds]
    shelves = shelved(bench)
    behind, stale = _behind(bench)
    if kind is None:
        return page(
            request,
            "library.html",
            person=bench.person,
            shelves=shelves,
            stale=stale,
            behind=behind,
        )
    if kind not in words:
        raise NotFound.raw(
            "no kind %(kind)s: the kinds are %(kinds)s",
            kind=repr(kind),
            kinds=", ".join(words),
        )
    found = [] if kind == "case" else listed(bench, kind)
    every = families.families(bench) if kind == "case" else []
    picked = set(tag or ())
    if kind == "case":
        said = read.abouts(bench.rows, [Subject(family=f.id) for f in every])
        described = {s.family: a.description for s, a in said.items()}
    else:
        said = read.abouts(bench.rows, [Subject(thread=t.id) for t, _ in found])
        described = {s.thread: a.description for s, a in said.items()}
    schemas_seen = [
        (t.head.digest, t.name or t.title)
        for t in api.threads(bench, "expectation_schema")
    ]
    held = (
        _schemas_of(bench, [t for t, _ in found])
        if kind == "expectation" and schema
        else {}
    )
    shown = [
        t
        for t, _ in found
        if _found(q, t.name or t.title, t.owner, t.tags, described.get(t.id))
        and (not held or held.get(t.id) == schema)
    ]
    cases = [
        f
        for f in every
        if picked <= set(f.tags)
        and _found(q, f.name, f.owner, f.tags, described.get(f.id))
    ]
    listing = _Listing(kind, sorted(picked), q.strip(), schema)
    return page(
        request,
        "library.html",
        200 if typed is None else 422,
        person=bench.person,
        typed=typed,
        shelves=shelves,
        stale=stale,
        behind=behind,
        about=next(s.kinds[kind] for s in SHELVES if kind in s.kinds),
        word=kind,
        listing=listing,
        every=pick == "all",
        of=len(every) if kind == "case" else len(found),
        threads=own_first(bench, shown),
        described=described,
        origins={} if kind == "case" else _origins(bench, kind, [t for t, _ in found]),
        purposes={
            t.id: pgettext("purpose", _PURPOSES[p]) for t, p in found if p is not None
        },
        begun=kind in _BEGUN,
        cases=sorted(
            cases, key=lambda f: (f.owner != bench.person.login, f.name.lower())
        ),
        tags=sorted({t for f in every for t in f.tags}),
        picked=picked,
        schemas=schemas_seen if kind in ("case", "expectation") else [],
        deleted=[
            (f"/cases/{f.id}", f.name) for f in families.families(bench, deleted=True)
        ]
        if kind == "case"
        else [
            (f"/threads/{t.id}", t.name or t.title)
            for t, _ in listed(bench, kind, deleted=True)
        ],
    )


@dataclass(frozen=True)
class _Listing:
    kind: str
    tags: list[str]
    q: str
    schema: str | None

    def link(self, tags: list[str] | None = None, **more: str) -> str:
        given = [("kind", self.kind)]
        given += [("tag", t) for t in (self.tags if tags is None else tags)]
        given += [("q", self.q)] if self.q else []
        given += [("schema", self.schema)] if self.schema else []
        return "/library?" + urlencode([*given, *more.items()])

    def toggled(self, tag: str) -> str:
        tags = [t for t in self.tags if t != tag] + ([] if tag in self.tags else [tag])
        return self.link(sorted(tags))


def _found(
    q: str, name: str, owner: str | None, tags: list[str], description: str | None
) -> bool:
    held = " ".join([name, owner or "", *tags, description or ""]).casefold()
    return all(word in held for word in q.casefold().split())


def _schemas_of(bench: Bench, found: list[schemas.Thread]) -> dict[int, str]:
    fetched = dict(bench.rows.components([t.head.digest for t in found]))
    return {
        t.id: resolve(
            fetched.__getitem__, t.head.digest, Expectation
        ).expectation_schema
        for t in found
    }


def _origins(
    bench: Bench, word: str, seen: list[schemas.Thread]
) -> dict[int, schemas.Thread | None]:
    held = [t for kind in KINDS[word] for t in bench.rows.threads(kind)]
    forked = {t.id: t.forked_from for t in held if t.forked_from is not None}
    if not forked:
        return {}
    at = {e.id: e.thread for e in bench.rows.edits([t.id for t in held])}
    shown = {t.id: t for t in seen}
    return {t: shown.get(at[e]) for t, e in forked.items() if e in at}


@router.get("/library/new")
def beginning(
    request: Request,
    bench: BenchDep,
    kind: str,
    configuration: int | None = None,
    into: str | None = None,
) -> Response:
    model = _begun(kind)
    if model is Translations:
        return _beginning_translations(request, bench, configuration, into)
    with refused(NotFound):
        given = _given(bench, request)
        found = fresh(model, given)
        if model is Scorer and "entry_point" not in given:
            return _shipped(request, code_of(bench))
        found = _drawn(bench, model, found)
    return _begin_page(request, bench, kind, model, found)


@router.post("/library/new")
def writing(
    request: Request,
    bench: BenchDep,
    kind: str,
    form: FormDep,
    configuration: int | None = None,
    into: str | None = None,
) -> Response:
    model = _begun(kind)
    name = str(form.get("name", "")).strip()
    if form.get("checking") and model is Translations:
        return JSONResponse({"refused": []})
    if model is Translations:
        refusals: list[str] = []
        try:
            made = translated(None, into or "", posted(form))
            if name:
                written = bench.new(made, name)
                return RedirectResponse(f"/threads/{written.edit.thread}", 303)
        except ValueError as e:
            if not refusable(e):
                raise
            refusals = [refusal_of(e)]
        return _beginning_translations(
            request, bench, configuration, into, refusals, 422
        )
    with refused(NotFound):
        found = fresh(model, _given(bench, request))
    if form.get("checking"):
        return _checked(bench, model, found, form)
    language = str(form.get("language", "")).strip() or None
    labels = str(form.get("labels", "{}"))
    declined: ValueError | None = None
    try:
        made = model.model_validate(parsed(found, form))
        if name:
            written = bench.new(
                made,
                name,
                language if isinstance(made, Component) else None,
                _labels(labels) if isinstance(made, Scorer) else None,
            )
            return RedirectResponse(f"/threads/{written.edit.thread}", 303)
    except ValueError as e:
        if not refusable(e):
            raise
        declined = e
    found, refusals = kept(found, form, declined)
    typed = Typed(refusals, name, language, labels)
    return _begin_page(request, bench, kind, model, found, typed)


# Policy: a form is read as it is typed as it is read when it is sent, so that the island
# holds it back while it would be refused rather than sending it to be.
def _checked(
    bench: Bench, model: type[BaseModel], found: list[Field], form: FormData
) -> Response:
    try:
        made = model.model_validate(parsed(found, form))
        if isinstance(made, Scorer):
            _ = _labels(str(form.get("labels", "{}")))
        if isinstance(made, Recipe):
            _ = compiled(bench, made)
    except ValueError as e:
        if not refusable(e):
            raise
        kept_found, rest = kept(found, form, e)
        refusals = [
            f"{f.name.replace('_', ' ')}: {f.refused}" for f in kept_found if f.refused
        ]
        return JSONResponse({"refused": [*refusals, *rest]})
    return JSONResponse({"refused": []})


def _picks_checked(
    bench: Bench,
    thread: int,
    head: int,
    recipe: dict[str, JsonValue],
    found: list[Field],
    form: FormData,
) -> Response:
    try:
        picked = parsed(found, form)
        given = {
            p: picked.get(p) for p in RECIPE_PARTS if picked.get(p) != recipe.get(p)
        }
        variation = bench.variation(thread, cast(dict[str, str | None], given), head)
        if variation.varied is not None:
            _ = compiled(bench, variation.varied)
    except ValueError as e:
        if not refusable(e):
            raise
        return JSONResponse({"refused": [refusal_of(e)]})
    return JSONResponse({"refused": []})


def _labels(typed: str) -> Labels:
    try:
        return schemas.Labels.model_validate_json(typed).given()
    except ValidationError as e:
        raise Invalid.of("labels: %(refused)s", refused=e.errors()[0]["msg"]) from None


def _begin_page(
    request: Request,
    bench: Bench,
    kind: str,
    model: type[Component] | type[Recipe],
    found: list[Field],
    typed: Typed | None = None,
) -> Response:
    titles = {
        d: bench.title(d)
        for f in found
        if not f.editable and f.kinds
        for d in (f.value if isinstance(f.value, list) else [f.value])
        if isinstance(d, str)
    }
    return page(
        request,
        "begun.html",
        200 if typed is None else 422,
        person=bench.person,
        word=kind,
        action=f"{request.url.path}?{request.url.query}",
        fields=found,
        picked={
            f.name: choices(bench, f.kinds, f.value, purpose(model))
            for f in found
            if f.editable and f.kinds
        },
        titles=titles,
        links=_links(bench, titles),
        languaged=model is not Recipe
        and model.model_fields["kind"].default in LANGUAGE_KINDS,
        labels=schemas.Labels().model_dump(mode="json") if model is Scorer else None,
        typed=typed,
        **_edited(bench, model, found),
    )


# Policy: a new scorer pins the code chatddx ships, as it is shown and not asked.
def _shipped(request: Request, code: schemas.ScorerCode) -> Response:
    given = [("f.entry_point", code.entry_point), ("f.version", str(code.version))]
    query = urlencode([*request.query_params.multi_items(), *given])
    return RedirectResponse(f"{request.url.path}?{query}", 303)


def _beginning_translations(
    request: Request,
    bench: Bench,
    configuration: int | None,
    into: str | None,
    refusals: list[str] | None = None,
    status: int = 200,
) -> Response:
    entries = None
    if configuration is not None and into:
        try:
            entries = begun(bench, configuration, language_tag(into))
        except NotFound as e:
            raise Refusing(422, e) from None
        except ValueError as e:
            if not refusable(e):
                raise
            refusals, status = [*(refusals or []), refusal_of(e)], 422
    return page(
        request,
        "begun.html",
        status,
        person=bench.person,
        word="translations",
        action=f"{request.url.path}?{request.url.query}",
        configurations=[
            (t.id, t.name or t.title)
            for t in own_first(
                bench, api.threads(bench, "configuration", purpose="generation")
            )
        ],
        configuration=configuration,
        into=into,
        entries=entries,
        typed=None if refusals is None else Typed(refusals),
    )


def _given(bench: Bench, request: Request) -> dict[str, str]:
    given = {
        k.removeprefix("f."): v
        for k, v in request.query_params.items()
        if k.startswith("f.")
    }
    if families := request.query_params.getlist("family"):
        held = [bench.family(int(f)) for f in families]
        given["cases"] = json.dumps(list(dict.fromkeys(f.case for f in held)))
    return given


# Policy: a new trial is begun with what a start of a variation takes when none is
# given.
def _drawn(
    bench: Bench, model: type[Component] | type[Recipe], found: list[Field]
) -> list[Field]:
    if model is not Trial:
        return found
    cases = next(f.value for f in found if f.name == "cases")
    begun: dict[str, JsonValue] = {"seeds": list(suggest_seeds(1))}
    if isinstance(cases, list) and cases:
        begun["cleanup"] = list(bench.cleanup([str(c) for c in cases]))
    return [
        replace(f, value=begun[f.name], given=True)
        if f.editable and f.name in begun
        else f
        for f in found
    ]


def _begun(kind: str) -> type[Component] | type[Recipe]:
    if kind not in _BEGUN:
        raise NotFound.raw(
            "no %(kind)s is begun here: what is begun here is %(kinds)s",
            kind=kind,
            kinds=", ".join(_BEGUN),
        )
    if kind == "configuration":
        return Recipe
    return BY_KIND[KINDS[kind][0]]


@router.get("/threads/{thread}")
def thread_page(
    request: Request,
    bench: BenchDep,
    thread: int,
    version: int | None = None,
    into: str | None = None,
) -> Response:
    return _thread_page(request, bench, thread, version, into)


def _thread_page(
    request: Request,
    bench: Bench,
    thread: int,
    version: int | None = None,
    into: str | None = None,
    typed: Typed | None = None,
    kept: list[Field] | None = None,
) -> Response:
    shown = api.thread(bench, thread)
    word = word_of(shown.kind)
    if word in IN_REVIEW:
        raise NotFound.raw(
            "no page of %(kind)s %(thread)s: it is in Review, in the case it goes with",
            kind=display_kind(word),
            thread=thread,
        )
    versions = api.edits(bench, thread)
    last = max(v.version for v in versions)
    current = versions[-1].version
    at = current if version is None else version
    if not 1 <= at <= last:
        raise NotFound.raw(
            "no version %(at)s of %(kind)s %(thread)s: it has %(versions)s",
            at=at,
            kind=display_kind(word),
            thread=thread,
            versions=last,
        )
    edit = next(v for v in reversed(versions) if v.version == at)
    first = next(i for i, v in enumerate(versions) if v.version == at)
    saved_on = None if first == 0 else versions[first - 1]
    held = bench.store.get(edit.digest)
    before = None if saved_on is None else bench.store.get(saved_on.digest)
    origin = None
    if shown.forked_from is not None:
        found = bench.rows.edit(shown.forked_from)
        try:
            origin = None if found is None else api.thread(bench, found.thread)
        except NotFound:
            origin = None
    mine = shown.owner == bench.person.login
    proposal = api.proposal(bench, thread) if mine and not shown.deleted else None
    latest = at == current
    gone = unshipped(held) if isinstance(held, Scorer) else None
    editable = mine and latest and not shown.deleted and gone is None
    body = held.model_dump(mode="json")
    words = None
    if isinstance(held, Translations):
        digests = [v.digest for v in versions]
        try:
            words = translating(bench, held, digests, into)
        except ValueError as e:
            if not refusable(e):
                raise
            typed = Typed([*(typed.refused if typed else []), refusal_of(e)])
            words = translating(bench, held, digests, None)
    written = editable and held.kind_name in WRITTEN and words is None
    found = fields(type(held), body, _editable(held, body) if written else ())
    recipe = _recipe(bench, edit.id) if shown.kind == "skeleton" else None
    parts = (
        None
        if recipe is None
        else fields(Recipe, recipe, RECIPE_PARTS if editable else ())
    )
    if kept is not None and parts is not None:
        parts = kept
    elif kept is not None:
        found = kept
    every = [*found, *(parts or [])]
    titles = {site.digest: bench.title(site.digest) for site in held.refs()}
    titles |= {
        f.value: bench.title(f.value)
        for f in parts or []
        if f.kinds and isinstance(f.value, str)
    }
    earlier = None
    if recipe is not None and before is not None:
        earlier = None if saved_on is None else _recipe(bench, saved_on.id)
    if earlier is not None:
        titles |= {
            d: bench.title(d)
            for p in RECIPE_PARTS
            if isinstance(d := earlier.get(p), str) and d not in titles
        }
    composed = [] if earlier is None or recipe is None else changes(earlier, recipe)
    return page(
        request,
        "thread.html",
        200 if typed is None else 422,
        person=bench.person,
        typed=typed,
        thread=shown,
        word=word,
        in_world=word in IN_WORLD,
        home=_home(word, thread),
        versions=versions,
        at=at,
        last=last,
        current=current,
        saved=versions[first],
        edit=edit,
        saved_on=None if saved_on is None else saved_on.version,
        fields=found,
        parts=parts,
        editable=any(f.editable for f in every),
        translating=words,
        translatable=editable and words is not None,
        picked={
            f.name: choices(bench, f.kinds, f.value, purpose(type(held)))
            for f in every
            if f.editable and f.kinds
        },
        titles=titles,
        languaged=written and held.kind_name in LANGUAGE_KINDS,
        labels=None
        if not written or not isinstance(held, Scorer)
        else (edit.labels or schemas.Labels()).model_dump(mode="json"),
        checked=checked(bench, held)
        if held.kind_name in WRITTEN and not gone
        else None,
        links=_links(bench, titles),
        composed=bool(composed),
        changed=None
        if before is None
        else composed or changes(before.model_dump(mode="json"), body),
        revertible=mine and not latest and not shown.deleted and shown.kind in AUTHORED,
        authored=shown.kind in AUTHORED,
        origin=origin,
        mine=mine,
        proposal=proposal,
        changes=[]
        if proposal is None
        else [
            (v.path, json.dumps(v.base), json.dumps(v.fork)) for v in proposal.varies
        ],
        unshipped=gone if latest and not shown.deleted else None,
        ran=_ran(bench, versions) if shown.kind == "trial" else None,
        **_edited(bench, type(held), found),
    )


def _edited(bench: Bench, model: type[BaseModel], found: list[Field]) -> dict[str, Any]:
    made = editors(bench, model, found)
    return {} if made is None else {"island": "library", "editing": made}


def _links(bench: Bench, digests: Iterable[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for digest in digests:
        if bench.rows.kind(digest) == "case":
            family = catalog.families.family_of(bench.rows, digest)
            about = (
                None
                if family is None
                else read.about(bench.rows, Subject(family=family))
            )
            if about is not None and sees(bench.person.id, about):
                found[digest] = f"/cases/{family}"
        elif (held := bench.holder(digest)) is not None:
            found[digest] = f"/threads/{held[0].thread}"
    return found


# Policy: an expectation stays of the case and the schema it was written for; Review
# carries it to a case that replaces its own.
def _editable(held: Component, body: dict[str, JsonValue]) -> list[str]:
    fixed = ("case", "expectation_schema") if isinstance(held, Expectation) else ()
    return [name for name in body if name not in fixed]


def _ran(
    bench: Bench, versions: list[schemas.Versioned]
) -> list[tuple[int, RunStarted, Titled]]:
    at = {v.digest: v.version for v in versions}
    return [(at[r.trial], r, bench.titled(r)) for r in bench.runs() if r.trial in at]


def _recipe(bench: Bench, edit: int) -> dict[str, JsonValue] | None:
    found = bench.rows.edit(edit)
    held = None if found is None else catalog.threads.recipe(bench.rows, found)
    return None if held is None else held.model_dump(mode="json")


def _back(thread: int, next: str | None) -> RedirectResponse:
    return RedirectResponse(within(next or f"/threads/{thread}"), 303)


@router.post("/threads/{thread}/said")
def saying(
    request: Request,
    bench: BenchDep,
    thread: int,
    name: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    tags: Annotated[str, Form()] = "",
    shared: Annotated[str, Form()] = "",
) -> Response:
    given: dict[str, Any] = {
        "name": name.strip() or None,
        "description": description.strip() or None,
        "tags": _listed_words(tags),
        "collaborators": _listed_words(shared),
    }
    try:
        _ = bench.say(Subject(thread=thread), **given)
    except (ValueError, NotFound) as e:
        if isinstance(e, ValueError) and not refusable(e):
            raise
        about = {"name": name, "description": description, "tags": tags}
        typed = Typed([refusal_of(e)], about={**about, "shared": shared})
        return _thread_page(request, bench, thread, typed=typed)
    return _back(thread, None)


def _listed_words(given: str) -> list[str]:
    return sorted({w.strip() for w in given.split(",") if w.strip()})


@router.post("/threads/{thread}/delete")
def deleting(bench: BenchDep, thread: int) -> Response:
    with refused():
        _ = bench.say(Subject(thread=thread), deleted=True)
    return _back(thread, None)


@router.post("/threads/{thread}/restore")
def restoring(bench: BenchDep, thread: int) -> Response:
    with refused():
        _ = bench.say(Subject(thread=thread), deleted=False)
    return _back(thread, None)


@router.post("/threads/{thread}/leave")
def leaving(bench: BenchDep, thread: int) -> Response:
    word = word_of(api.thread(bench, thread).kind)
    with refused(NotFound):
        _ = bench.leave(Subject(thread=thread))
    return RedirectResponse(_home(word, thread), 303)


def _home(word: str, thread: int) -> str:
    if word in IN_WORLD:
        return f"/world#{IN_WORLD[word]}-{thread}"
    return f"/library?kind={word}"


@router.post("/threads/{thread}/edit")
def editing(request: Request, bench: BenchDep, thread: int, form: FormDep) -> Response:
    shown = api.thread(bench, thread)
    held = bench.store.get(shown.head.digest)
    with refused():
        head = int(str(form.get("head", "")))
    if form.get("checking") and isinstance(held, Translations):
        return JSONResponse({"refused": []})
    if isinstance(held, Translations):
        into = str(form.get("into", ""))
        try:
            made = translated(held, into, posted(form))
            _ = bench.edit(thread, head, made)
        except ValueError as e:
            if not refusable(e):
                raise
            return _thread_page(
                request, bench, thread, None, into or None, Typed([refusal_of(e)])
            )
        moved = f"?{urlencode({'into': into})}" if into in made.into else ""
        return _back(thread, f"/threads/{thread}{moved}")
    if shown.kind == "skeleton":
        recipe = _recipe(bench, shown.head.id)
        if recipe is None:
            raise Invalid.of(
                "configuration %(thread)s is written by hand: it has no recipe to "
                + "pick parts of",
                thread=thread,
            )
        found = fields(Recipe, recipe, RECIPE_PARTS)
        if form.get("checking"):
            return _picks_checked(bench, thread, head, recipe, found, form)
        try:
            picked = parsed(found, form)
            replaced = {p: picked.get(p) for p in RECIPE_PARTS}
            given = {p: d for p, d in replaced.items() if d != recipe.get(p)}
            variation = bench.variation(
                thread, cast(dict[str, str | None], given), head
            )
            _ = bench.edit(thread, head, variation)
        except ValueError as e:
            if not refusable(e):
                raise
            found, refusals = kept(found, form, e)
            return _thread_page(
                request, bench, thread, typed=Typed(refusals), kept=found
            )
        return _back(thread, None)
    body = held.model_dump(mode="json")
    found = fields(type(held), body, _editable(held, body))
    if form.get("checking"):
        return _checked(bench, type(held), found, form)
    language = str(form.get("language", "")).strip() or None
    labels = str(form.get("labels", "{}"))
    try:
        made = type(held).model_validate(parsed(found, form))
        _ = bench.edit(
            thread,
            head,
            made,
            language=language if held.kind_name in LANGUAGE_KINDS else None,
            labels=_labels(labels) if isinstance(made, Scorer) else None,
        )
    except ValueError as e:
        if not refusable(e):
            raise
        found, refusals = kept(found, form, e)
        typed = Typed(refusals, language=language, labels=labels)
        return _thread_page(request, bench, thread, typed=typed, kept=found)
    return _back(thread, None)


@router.post("/threads/{thread}/revert")
def reverting(
    bench: BenchDep,
    thread: int,
    head: Annotated[int, Form()],
    edit: Annotated[int, Form()],
) -> Response:
    earlier = next((v for v in api.edits(bench, thread) if v.id == edit), None)
    if earlier is None:
        raise Invalid.raw(
            "edit %(edit)s isn't a version of thread %(thread)s",
            edit=edit,
            thread=thread,
        )
    held = (
        bench.variation(thread, None, edit)
        if api.thread(bench, thread).kind == "skeleton"
        else bench.store.get(earlier.digest)
    )
    labels = read.labels(bench.rows, edit) if isinstance(held, Scorer) else None
    with refused():
        _ = bench.edit(thread, head, held, labels=labels)
    return _back(thread, None)


@router.post("/threads/{thread}/fork")
def forking(bench: BenchDep, thread: int, name: Annotated[str, Form()]) -> Response:
    if not name.strip():
        raise Invalid.raw("a fork is named")
    with refused():
        made = bench.fork(thread, name.strip())
    return RedirectResponse(f"/threads/{made.edit.thread}", 303)


@router.post("/threads/{thread}/update")
def updating(
    bench: BenchDep,
    thread: int,
    head: Annotated[int, Form()],
    next: Annotated[str | None, Form()] = None,
) -> Response:
    with refused():
        _ = bench.update(thread, head)
    return _back(thread, next)


@router.post("/library/update")
def updating_all(request: Request, bench: BenchDep) -> Response:
    done = bench.update_all()
    shown = {u.thread: api.thread(bench, u.thread) for u in done}
    return page(
        request,
        "updated.html",
        person=bench.person,
        updated=[
            (shown[u.thread], u.remodelled) for u in done if u.written is not None
        ],
        refused=[
            (shown[u.thread], refusal_of(u.refused))
            for u in done
            if u.refused is not None
        ],
    )


@router.post("/threads/{thread}/take")
def taking(
    bench: BenchDep, thread: int, next: Annotated[str | None, Form()] = None
) -> Response:
    with refused():
        made = bench.take_from(thread)
    return _back(made, next)


@router.post("/threads/{thread}/carry")
def carrying(
    bench: BenchDep,
    thread: int,
    head: Annotated[int, Form()],
    case: Annotated[str, Form()],
    next: Annotated[str | None, Form()] = None,
) -> Response:
    edit, _ = bench.thread(thread, "expectation")
    held = resolve(bench.store.get, edit.digest, Expectation)
    carried = Expectation(
        case=case, expectation_schema=held.expectation_schema, data=held.data
    )
    with refused():
        _ = bench.edit(thread, head, carried)
    return _back(thread, next)
