from collections.abc import Mapping, Sequence
from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import JsonValue

from chatddx import catalog
from chatddx.bench import (
    KINDS,
    WRITTEN,
    Bench,
    Carried,
    Endpoint,
    NotFound,
    Proposed,
    Reach,
    TriedVariation,
    Written,
    word_of,
)
from chatddx.catalog import Subject, read, titles
from chatddx.catalog.language import edit_languages
from chatddx.catalog.titles import describe
from chatddx.factors.base import Component, Finding, Invalid, resolve
from chatddx.factors.facts import Landing
from chatddx.factors.kinds import BY_KIND
from chatddx.factors.request import (
    RECIPE_PARTS,
    Compilation,
    Purpose,
    Recipe,
    Run,
    Slot,
    translated,
)
from chatddx.factors.scoring import Expectation
from chatddx.factors.trial import suggest_seeds
from chatddx.store.cache import Cache, catalogued

from . import schemas
from .people import BenchDep
from .state import refused

router = APIRouter(tags=["threads"])

type _Asked = tuple[
    int, str, str | None, str | None, frozenset[str], bool, str | None, str | None
]

# Policy: so many listings held and no more; each is what a person was shown of a kind
# under the filters asked, held while the catalog's version stands, as the threads it
# lists and how each is told (titles, whether it is outdated) are read from the catalog,
# the components and the inventory alone, a database being served one World, besides
# logins, which never change.
_THREADS: Cache[_Asked, tuple[schemas.Thread, ...]] = Cache(1_000)


def login(bench: Bench, person: int | None) -> str | None:
    return None if person is None else bench.login(person)


def _edit_of(bench: Bench, edit: catalog.Edit, kind: str | None = None) -> schemas.Edit:
    if kind is None:
        kind = catalog.threads.thread(bench.rows, edit.thread).kind
    labels = None
    if kind == "scorer":
        labels = schemas.Labels.of(read.labels(bench.rows, edit.id))
    return schemas.Edit(
        id=edit.id,
        digest=edit.digest,
        compilation=edit.compilation,
        based_on=edit.based_on,
        by=bench.login(edit.by),
        at=edit.at,
        labels=labels,
    )


def thread_of(
    bench: Bench,
    kind: str,
    edit: catalog.Edit,
    about: catalog.About,
    languages: Mapping[int, str | None] | None = None,
) -> schemas.Thread:
    if languages is None:
        languages = edit_languages(bench.rows, [edit])
    return schemas.Thread(
        id=edit.thread,
        kind=kind,
        word=word_of(kind),
        name=about.name,
        title=titles.title(bench.rows, edit.thread),
        owner=login(bench, about.owner),
        tags=sorted(about.tags),
        language=languages[edit.id],
        translated=_translated(bench, edit),
        head=_edit_of(bench, edit, kind),
        outdated=bench.outdated(edit, kind),
        expecting=_expecting(bench, edit, about) if kind == "expectation" else None,
    )


# Policy: an expectation with no name is said by its case, in the reader's locale, rather
# than by a title derived in English.
def _expecting(
    bench: Bench, edit: catalog.Edit, about: catalog.About
) -> schemas.CaseTitle | None:
    if about.name is not None:
        return None
    case = resolve(bench.store.get, edit.digest, Expectation).case
    return schemas.CaseTitle.of(bench.titled_case(case))


def _translated(bench: Bench, edit: catalog.Edit) -> list[str]:
    if edit.compilation is None:
        return []
    recipe = resolve(bench.store.get, edit.compilation, Compilation).recipe
    return list(translated(recipe, bench.store.get))


@router.get("/threads")
def threads(
    bench: BenchDep,
    kind: Annotated[str, Query(description=f"one of {', '.join(KINDS)}")],
    name: str | None = None,
    owner: Annotated[str | None, Query(description="a login")] = None,
    tag: Annotated[list[str] | None, Query(description="any of these")] = None,
    deleted: Annotated[
        bool, Query(description="the person's own deleted threads instead")
    ] = False,
    purpose: Annotated[
        Purpose | None,
        Query(description="a configuration's, generation unless given"),
    ] = None,
    answers: Annotated[
        str | None,
        Query(description="a configuration's: the title of its answer's JSON Schema"),
    ] = None,
) -> list[schemas.Thread]:
    if kind not in KINDS:
        raise HTTPException(422, f"no kind {kind!r}: the kinds are {', '.join(KINDS)}")
    if purpose is not None and kind != "configuration":
        raise HTTPException(422, "only a configuration has a purpose")
    if answers is not None and kind != "configuration":
        raise HTTPException(422, "only a configuration answers")
    wanted = set(tag or ())
    if kind == "configuration":
        purpose = purpose or "generation"
    asked = (
        bench.person.id,
        kind,
        name,
        owner,
        frozenset(wanted),
        deleted,
        purpose,
        answers,
    )
    version = catalogued(bench.conn)
    if (held := _THREADS.get(bench.conn, asked, version)) is not None:
        return list(held)
    found = bench.threads(kind, deleted=deleted, purpose=purpose, answering=answers)
    shown = [
        (edit, about)
        for edit, about in found
        if (name is None or about.name == name)
        and (owner is None or login(bench, about.owner) == owner)
        and (not wanted or wanted & about.tags)
    ]
    languages = edit_languages(bench.rows, [edit for edit, _ in shown])
    [single] = KINDS[kind] if len(KINDS[kind]) == 1 else [None]
    made = tuple(
        thread_of(bench, single or bench.rows.kind(e.digest) or "", e, a, languages)
        for e, a in shown
    )
    _THREADS.put(bench.conn, asked, made, version)
    return list(made)


def _detail(bench: Bench, thread: int) -> schemas.ThreadDetail:
    edit, about = bench.thread(thread, deleted=True)
    found = catalog.threads.thread(bench.rows, thread)
    recipe = catalog.threads.recipe(bench.rows, edit)
    return schemas.ThreadDetail(
        **thread_of(bench, found.kind, edit, about).model_dump(),
        description=about.description,
        collaborators=sorted(bench.login(c) for c in about.collaborators),
        forked_from=found.forked_from,
        recipe=None if recipe is None else recipe.model_dump(mode="json"),
        deleted=about.deleted,
    )


@router.get("/threads/{thread}")
def thread(bench: BenchDep, thread: int) -> schemas.ThreadDetail:
    return _detail(bench, thread)


@router.get("/threads/{thread}/edits")
def edits(bench: BenchDep, thread: int) -> list[schemas.Versioned]:
    _ = bench.thread(thread, deleted=True)
    kind = catalog.threads.thread(bench.rows, thread).kind
    numbered = catalog.threads.versions(bench.rows, thread)
    return [
        schemas.Versioned(
            **_edit_of(bench, e, kind).model_dump(), version=numbered[e.id]
        )
        for e in catalog.threads.history(bench.rows, thread)
    ]


def _at(bench: Bench, varied: TriedVariation, model: str | None) -> Endpoint | str:
    try:
        return bench.at(varied, model=model)
    except (NotFound, ValueError) as e:
        if model is not None and varied.recipe is None:
            raise HTTPException(422, str(e)) from None
        return str(e)


def component_of(doc: Mapping[str, JsonValue]) -> Component:
    kind = doc.get("kind")
    if not isinstance(kind, str) or kind not in WRITTEN:
        raise ValueError(
            f"{kind!r} isn't a kind a person writes: the kinds are "
            + ", ".join(sorted(WRITTEN))
        )
    cls = BY_KIND[kind]
    if doc.get("v", cls.schema_version) != cls.schema_version:
        raise ValueError(f"{kind} is at v{cls.schema_version}, not v{doc['v']}")
    return cls.model_validate({k: v for k, v in doc.items() if k != "v"})


def _part_of(
    bench: Bench, variation: TriedVariation, part: str, landed: Landing | None = None
) -> schemas.Part:
    held = variation.held(part)
    return schemas.Part(
        part=part,
        digest=held,
        title=None if held is None else bench.title(held),
        summary=None if held is None else describe(bench.store.get(held), bench.title),
        replaced=part in variation.parts,
        landed=None if landed is None else landed.level,
        nearest=[] if landed is None else list(landed.nearest),
    )


def _reach_of(reach: Reach) -> schemas.Reach:
    return schemas.Reach(
        scorer=reach.thread,
        name=reach.scorer,
        view=reach.view,
        label=reach.label,
        offered=reach.offered,
        cases=reach.cases,
        missing=[f.id for f in reach.missing],
        choosing=[f.id for f in reach.choosing],
    )


@router.get("/threads/{thread}/variation")
def variation(
    bench: BenchDep, thread: int, query: Annotated[schemas.Varying, Query()]
) -> schemas.Variation:
    with refused():
        varied = bench.variation(thread, query.given(), query.head)
        skeleton = bench.skeleton(varied)
        landed = bench.landed(varied)
        at = _at(bench, varied, query.under)
    engine = None if isinstance(at, str) else at.engine
    seed = suggest_seeds(1)[0] if query.seed is None else query.seed
    families = bench.families(query.tag)
    carried: list[Carried] = []
    if families and skeleton.purpose != "judge":
        with refused():
            carried = bench.languages(varied, [f.case for f in families])
    findings = None
    if engine is not None:
        findings = [
            schemas.Finding.of(f)
            for f in bench.findings(varied, engine, seed, carried or None)
        ]
    family_of = {f.case: f.id for f in families}
    parts = None
    if varied.recipe is not None:
        parts = [_part_of(bench, varied, p, landed.get(p)) for p in RECIPE_PARTS]
    held = bench.holder(skeleton.digest, varied.varied)
    return schemas.Variation(
        head=_edit_of(bench, varied.configuration, "skeleton"),
        label=varied.label,
        skeleton=skeleton.digest,
        held_by=None if held is None else thread_of(bench, "skeleton", *held),
        greedy=skeleton.greedy,
        parts=parts,
        seed=seed,
        request=bench.request(varied, engine, seed),
        model=None if isinstance(at, str) else bench.handle(at.model.digest).name,
        problem=at if isinstance(at, str) else None,
        findings=findings,
        languages=[
            schemas.Carried(
                language=c.language,
                families=[family_of[case] for case in c.cases],
                translated=c.translated,
                skeleton=None if c.skeleton is None else c.skeleton.digest,
                refused=c.refused,
                untranslated=c.untranslated,
            )
            for c in carried
        ],
        reach=[_reach_of(r) for r in bench.reach(varied, families)],
    )


def made(
    request: Request,
    response: Response,
    bench: Bench,
    thread: int,
    findings: list[Finding],
) -> schemas.MadeThread:
    response.headers["Location"] = request.app.url_path_for("thread", thread=thread)
    found = [schemas.Finding.of(f) for f in findings]
    return schemas.MadeThread(**_detail(bench, thread).model_dump(), findings=found)


def _configures(bench: Bench, thread: int) -> bool:
    found = bench.rows.thread(thread)
    return found is not None and found.kind in KINDS["configuration"]


def _check_given(configuration: bool, given: schemas.NewFork | schemas.NewEdit) -> None:
    if configuration and (given.component is not None or given.language is not None):
        raise HTTPException(
            422, "a configuration is written with parts, not a component"
        )
    if not configuration and given.parts.given():
        raise HTTPException(422, "only a configuration has parts")
    if (
        not configuration
        and isinstance(given, schemas.NewFork)
        and given.head is not None
    ):
        raise HTTPException(
            422,
            "only a configuration is forked from an edit: another kind from a component",
        )
    if configuration and given.labels is not None:
        raise HTTPException(422, "only a scorer has labels")


@router.post("/threads", status_code=201)
def new(
    request: Request, response: Response, bench: BenchDep, given: schemas.NewThread
) -> schemas.MadeThread:
    with refused():
        held = (
            Recipe.model_validate(given.recipe)
            if given.component is None
            else component_of(given.component)
        )
        labels = None if given.labels is None else given.labels.given()
        written = bench.new(held, given.name, given.language, labels)
    return made(request, response, bench, written.edit.thread, written.findings)


@router.post("/threads/{thread}/forks", status_code=201)
def fork(
    request: Request,
    response: Response,
    bench: BenchDep,
    thread: int,
    given: schemas.NewFork,
) -> schemas.MadeThread:
    configuration = _configures(bench, thread)
    _check_given(configuration, given)
    with refused():
        held = (
            bench.variation(thread, given.parts.given(), given.head)
            if configuration
            else None
            if given.component is None
            else component_of(given.component)
        )
        labels = None if given.labels is None else given.labels.given()
        written = bench.fork(thread, given.name, held, given.language, labels)
    return made(request, response, bench, written.edit.thread, written.findings)


@router.post(
    "/threads/{thread}/edits",
    status_code=201,
    responses={
        200: {"description": "Unchanged: it is the head already"},
        409: {"description": "The thread has moved on since the head the edit names"},
    },
)
def edit(
    response: Response, bench: BenchDep, thread: int, given: schemas.NewEdit
) -> schemas.MadeEdit:
    configuration = _configures(bench, thread)
    _check_given(configuration, given)
    with refused():
        if configuration:
            held = bench.variation(thread, given.parts.given())
        elif given.component is None:
            raise ValueError("an edit holds a component")
        else:
            held = component_of(given.component)
        labels = None if given.labels is None else given.labels.given()
        written = bench.edit(thread, given.head, held, given.language, labels)
    if written.what == "unchanged":
        response.status_code = 200
    return _made_edit(bench, written)


@router.post("/threads/{thread}/drafts")
def draft(bench: BenchDep, thread: int, given: schemas.Draft) -> schemas.Drafting:
    """The texts a configuration would hold with the chunks drafted, and the
    translations given carried over to them, writing nothing."""
    with refused():
        held, into = bench.drafted(
            thread,
            given.head,
            _drafted(given.before),
            _drafted(given.after),
            given.translations,
        )
    return schemas.Drafting(
        texts={p: list(t) for p, t in held.items()}, translations=into
    )


@router.post("/threads/{thread}/previews")
def preview(bench: BenchDep, thread: int, given: schemas.Preview) -> schemas.Previewed:
    """The request a configuration would send with the chunks, model and
    translations drafted, writing nothing."""
    with refused():
        made = bench.preview(
            thread,
            given.head,
            _drafted(given.chunks),
            given.model,
            given.translations,
            given.language,
        )
    traced = made.traced
    return schemas.Previewed(
        messages=[
            schemas.PreviewMessage(
                role=m.role, runs=_ran(m.runs, traced.appendix_layout)
            )
            for m in traced.messages
        ],
        request=made.request,
        contract=traced.skeleton.contract.model_dump(mode="json"),
    )


def _ran(
    runs: Sequence[Run | Slot], layout: tuple[Run, Run, Run]
) -> list[schemas.Stretch]:
    before, between, after = layout
    found: list[schemas.Stretch] = []
    for r in runs:
        match r:
            case Run():
                found.append(schemas.Stretch.model_validate(r.model_dump()))
            case Slot(slot="appendices"):
                laid = [before, 1, between, 2, after]
                for at in laid:
                    if isinstance(at, int):
                        found.append(schemas.Stretch(appendix=at))
                    elif at.text:
                        found.append(schemas.Stretch.model_validate(at.model_dump()))
            case Slot(slot=slot):
                found.append(schemas.Stretch(slot=slot))
    return found


@router.post(
    "/threads/{thread}/saves",
    status_code=201,
    responses={
        409: {
            "description": "A thread has moved on since the head the save was made on"
        }
    },
)
def save(
    request: Request,
    response: Response,
    bench: BenchDep,
    thread: int,
    given: schemas.NewSave,
) -> schemas.MadeThread:
    """Saves a configuration with the chunks given in place of its own, each written
    to its own thread first, as a version of it or, named, a fork or one of its own."""
    if not _configures(bench, thread):
        raise HTTPException(422, "only a configuration is saved with its parts")
    with refused():
        written = bench.compose(
            thread,
            given.head,
            _drafted(given.chunks),
            given.model,
            given.translations,
            given.name,
            given.independent,
        )
    return made(request, response, bench, written.edit.thread, written.findings)


def _drafted(given: Mapping[str, JsonValue]) -> dict[str, Component | None]:
    return {
        part: None if body is None else component_of(cast(dict[str, JsonValue], body))
        for part, body in given.items()
    }


def _made_edit(bench: Bench, written: Written) -> schemas.MadeEdit:
    return schemas.MadeEdit(
        **_edit_of(bench, written.edit).model_dump(),
        findings=[schemas.Finding.of(f) for f in written.findings],
        cases=written.cases,
    )


@router.post(
    "/threads/{thread}/takes",
    status_code=201,
    responses={
        409: {
            "description": "The person has their own expectation of the case under "
            + "that schema: replace it to take this one"
        }
    },
)
def take(
    request: Request,
    response: Response,
    bench: BenchDep,
    thread: int,
    given: schemas.NewTake,
) -> schemas.ThreadDetail:
    with refused():
        made = bench.take_from(thread, given.replace)
    response.headers["Location"] = request.app.url_path_for("thread", thread=made)
    return _detail(bench, made)


@router.patch("/threads/{thread}")
def say(bench: BenchDep, thread: int, given: schemas.Said) -> schemas.ThreadDetail:
    """Writes what the request changes of the person's own thread, a field left out
    staying as it is, and answers what holds afterwards.

    Costs a lookup per collaborator and what `Bench.say` reads and writes, then a read
    of the thread.
    """
    said(bench, Subject(thread=thread), given)
    return _detail(bench, thread)


def said(bench: Bench, subject: Subject, given: schemas.Said) -> None:
    """Says through `Bench.say` what `given` sets, leaving what it leaves unset as it
    is. Each collaborator is looked up here as well as by the bench, so that an unknown
    login is unprocessable rather than not found.
    """
    people = bench.people
    if missing := [c for c in given.collaborators or () if people.find(c) is None]:
        raise Invalid.of("no person %(login)s", login=repr(missing[0]))
    with refused():
        _ = bench.say(subject, **given.model_dump(exclude_unset=True))


@router.post("/threads/{thread}/leave", status_code=204)
def leave(bench: BenchDep, thread: int) -> Response:
    _ = bench.leave(Subject(thread=thread))
    return Response(status_code=204)


@router.get("/threads/{thread}/lineage")
def lineage(bench: BenchDep, thread: int) -> list[schemas.Kin]:
    found = bench.lineage(thread)
    languages = edit_languages(bench.rows, [k.edit for k in found])
    kind = catalog.threads.thread(bench.rows, thread).kind
    return [
        schemas.Kin(
            **thread_of(bench, kind, k.edit, k.about, languages).model_dump(),
            origin=k.origin,
            base=None if k.divergence is None else _edit_of(bench, k.divergence.base),
            varies=[] if k.divergence is None else _varied(k.divergence),
            behind=k.behind,
            deleted=k.about.deleted,
        )
        for k in found
    ]


@router.get("/threads/{thread}/proposal")
def proposal(bench: BenchDep, thread: int) -> schemas.Proposal | None:
    with refused():
        proposed = bench.proposal(thread)
    return None if proposed is None else _proposal_of(bench, proposed)


def _proposal_of(bench: Bench, proposed: Proposed) -> schemas.Proposal:
    diverged, held = proposed.divergence, proposed.proposal
    recipe = isinstance(held, Recipe)
    return schemas.Proposal(
        reasons=list(proposed.reasons),
        about=proposed.about,
        base=None if diverged is None else _edit_of(bench, diverged.base),
        origin_head=None if diverged is None else _edit_of(bench, diverged.origin_head),
        varies=[] if diverged is None else _varied(diverged),
        clashes=[] if diverged is None else diverged.clashes,
        remodelled=None
        if proposed.remodelled is None
        else schemas.Remodelled(was=proposed.remodelled[0], now=proposed.remodelled[1]),
        recipe=held.model_dump(mode="json") if recipe else None,
        component=None if recipe or held is None else held.model_dump(mode="json"),
        digest=proposed.digest,
        compilation=proposed.compilation,
        refused=None if proposed.refused is None else str(proposed.refused),
    )


def _varied(diverged: catalog.Divergence) -> list[schemas.Varied]:
    return [
        schemas.Varied(path=path, base=base, fork=fork)
        for path, (base, fork) in diverged.varies.items()
    ]


@router.post(
    "/threads/{thread}/update",
    status_code=201,
    responses={
        409: {"description": "The thread has moved on since the head the edit names"}
    },
)
def update(bench: BenchDep, thread: int, given: schemas.NewUpdate) -> schemas.MadeEdit:
    with refused():
        written = bench.update(thread, given.head, given.language)
    return _made_edit(bench, written)
