import json
from dataclasses import dataclass, replace
from typing import Annotated, Any
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Form, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from pydantic import JsonValue, ValidationError

from chatddx import catalog
from chatddx.api import (
    breakdown as api_breakdown,
    families as api_families,
    schemas,
    threads as api,
)
from chatddx.api.standing import Behind, Standing, baseline_cases, standing
from chatddx.bench import Bench, Handle, NotFound
from chatddx.curation.write import ARCHIVE
from chatddx.factors.base import Component, Finding, resolve
from chatddx.factors.facts import LEVELS, ContractFact, Refusal, Refused
from chatddx.factors.gathering import BASELINE
from chatddx.factors.kinds import BY_KIND
from chatddx.factors.request import (
    CHUNK_PARTS,
    INSERTS_BY_KIND,
    SLOTS_BY_PURPOSE,
    Recipe,
    Toolset,
    texts,
    translated,
)

from .mending import mend, placed
from .pages import BenchDep, configurations, page, refusal_of
from .scoring import unit_in
from .shelves import display_kind
from .titles import display_case

router = APIRouter()


@router.get("/compose")
def composing(request: Request, bench: BenchDep) -> Response:
    listed = configurations(bench)
    if listed:
        return RedirectResponse(f"/compose/{listed[0].id}", 303)
    return page(request, "compose.html", person=bench.person, configuration=None)


@router.get("/compose/{thread}")
def compose(
    request: Request,
    bench: BenchDep,
    thread: int,
) -> Response:
    query = _varying(request)
    shown = api.thread(bench, thread)
    if shown.kind != "skeleton":
        raise NotFound.of(
            "no configuration %(thread)s for %(login)s",
            thread=thread,
            login=bench.person.login,
        )
    varied = bench.variation(thread, None, query.head)
    recipe = varied.recipe
    judged = recipe is not None and recipe.purpose == "judge"
    models = [h for h, at in bench.handles() if at is not None]
    look = api.variation(bench, thread, query)
    versions = api.edits(bench, thread)
    at = next(i for i, v in enumerate(versions) if v.id == look.head.id)
    mine = shown.owner == bench.person.login
    proposal = api.proposal(bench, thread) if mine and not shown.deleted else None
    purpose = "judge" if judged else "generation"
    based = None if judged else _baseline(bench, shown, look.head.id)
    props: dict[str, Any] = {
        "configuration": shown.model_dump(mode="json"),
        "me": bench.person.login,
        "versions": [v.model_dump(mode="json") for v in versions],
        "head": look.head.id,
        "varied": bool(query.given()),
        "modelChoices": [
            t.model_dump(mode="json") for t in _choices(bench, "model", models)
        ],
        "facts": {
            d: _facts(bench, d)
            for d in {
                *(t.head.digest for t in _choices(bench, "model", models)),
                *([] if recipe is None else [recipe.model]),
            }
        },
        "toolChoices": _tool_choices(bench),
        "drafted": _drafted(
            bench, bench.variation(thread, query.given(), query.head).varied
        ),
        "configurations": [
            t.model_dump(mode="json")
            for t in api.threads(bench, "configuration", purpose=purpose)
        ],
        "cases": [] if judged else _cases(bench),
        "baseline": None
        if based is None
        else {
            "running": based.running,
            "behind": based.mendable,
            "whole": based.whole,
            "runs": [str(r) for r in based.runs],
        },
    }
    return page(
        request,
        "compose.html",
        person=bench.person,
        configuration=shown,
        configurations=_forks(bench, configurations(bench)),
        versions=versions,
        at=at,
        links=[linked(query, v.id, versions[-1].id) for v in versions],
        proposal=proposal,
        changes=[
            (
                display_kind(v.path.removeprefix("/recipe/")),
                _held(bench, v.base),
                _held(bench, v.fork),
            )
            for v in ([] if proposal is None else proposal.varies)
        ],
        baseline=based,
        props=props,
        island="compose",
    )


@router.get("/gatherings/{started}")
def gathered(
    request: Request, bench: BenchDep, started: UUID, view: int = 0
) -> Response:
    held = api_breakdown.gathering(bench, started)
    at = view if 0 <= view < len(held.views) else 0
    return page(
        request,
        "gathering.html",
        person=bench.person,
        held=held,
        at=at,
        titles={r.case: display_case(bench.titled_case(r.case)) for r in held.rows},
        units=[unit_in(bench, v.scorer, v.view) for v in held.views],
    )


@router.post("/compose/{thread}/runs")
def running_in_compose(
    bench: BenchDep, thread: int, head: Annotated[int | None, Form()] = None
) -> Response:
    shown = api.thread(bench, thread)
    if shown.kind != "skeleton":
        raise NotFound.of(
            "no configuration %(thread)s for %(login)s",
            thread=thread,
            login=bench.person.login,
        )
    if not (cases := baseline_cases(bench)):
        raise NotFound("this World names no baseline cases")
    stood = _stood(bench, shown, cases, head)
    back = f"/compose/{thread}" + ("" if head is None else f"?head={head}")
    # Policy: as in Review, a press made while its baseline is under way counts as made.
    if any(b.why == "under_way" for b in stood.behind):
        return RedirectResponse(back, 303)
    # Policy: a baseline whole as things are now is run again on seeds drawn anew, as
    # its seeds again would only repeat what it answered.
    if not stood.behind:
        stood = replace(stood, behind=[Behind("no_runs", rerun={})])
    # Policy: a baseline that can't run says why on the page it leads back to.
    _ = mend(bench, [stood], cases, BASELINE, bench.unscored)
    return RedirectResponse(back, 303)


@dataclass(frozen=True)
class Baseline:
    refusal: str | None
    outdated: bool
    untranslated: str | None
    findings: list[Finding]
    running: bool
    mendable: bool
    whole: bool
    runs: list[UUID]


def _cases(bench: Bench) -> list[dict[str, Any]]:
    return [
        {"family": f.id, "name": f.name, "tags": f.tags, "language": f.language}
        for f in api_families.families(bench)
    ]


def _baseline(bench: Bench, shown: schemas.ThreadDetail, head: int) -> Baseline | None:
    tag = bench.inventory.baseline
    cases = baseline_cases(bench)
    if tag is None or not cases:
        return None
    stood = _stood(bench, shown, cases, head)
    runs, behind = stood.runs, stood.behind
    refused = next((b.refusal for b in behind if b.refusal is not None), None)
    return Baseline(
        refusal=None if refused is None else refusal_of(refused),
        outdated=any(b.why == "outdated" for b in behind),
        untranslated=_tabless(
            bench, shown, head, [b.language for b in behind if b.why == "untranslated"]
        ),
        findings=_found(bench, shown, cases, head) if runs else [],
        running=any(b.why == "under_way" for b in behind),
        mendable=_mendable(behind),
        whole=not behind,
        runs=[r.run for r in runs],
    )


# Policy: a language the configuration has translations into has a tab of its own in
# Compose, which marks it while texts are left to translate there, so only one it has
# none into is said above it.
def _tabless(
    bench: Bench, shown: schemas.Thread, head: int, languages: list[str | None]
) -> str | None:
    if not languages or languages[0] is None:
        return None
    recipe = bench.variation(shown.id, {}, head).varied
    held = {} if recipe is None else translated(recipe, bench.store.get)
    return None if languages[0] in held else languages[0]


def _stood(
    bench: Bench, shown: schemas.Thread, cases: list[str], head: int | None
) -> Standing:
    [stood] = standing(bench, [shown], cases, BASELINE, bench.unscored, head)
    return stood


def _mendable(behind: list[Behind]) -> bool:
    return not any(b.why == "under_way" for b in behind) and any(
        b.rerun is not None or b.resume or b.rescore for b in behind
    )


def _found(
    bench: Bench, shown: schemas.ThreadDetail, cases: list[str], head: int
) -> list[Finding]:
    if (at_hand := placed(bench, shown, head)) is None:
        return []
    variation, at = at_hand
    return bench.findings(variation, at.engine, 0, bench.languages(variation, cases))


@dataclass(frozen=True)
class Forked:
    thread: schemas.Thread
    forks: list["Forked"]


def _forks(bench: Bench, listed: list[schemas.Thread]) -> list[Forked]:
    ids = {t.id for t in listed}
    under: dict[int | None, list[schemas.Thread]] = {}
    for t in listed:
        origin = catalog.threads.origin(bench.rows, t.id)
        under.setdefault(origin if origin in ids else None, []).append(t)

    def grown(t: schemas.Thread) -> Forked:
        return Forked(t, [grown(f) for f in under.get(t.id, [])])

    return [grown(t) for t in under.get(None, [])]


def _varying(request: Request) -> schemas.Varying:
    given: dict[str, Any] = {}
    for key, value in request.query_params.multi_items():
        if key == "tag":
            given.setdefault("tag", []).append(value)
        else:
            given[key] = value
    try:
        return schemas.Varying.model_validate(given)
    except ValidationError as e:
        errors = [{**error, "loc": ("query", *error["loc"])} for error in e.errors()]
        raise RequestValidationError(errors) from None


def linked(query: schemas.Varying, head: int, latest: int) -> str:
    given: list[tuple[str, str | int]] = [
        (part, digest or "") for part, digest in query.given().items()
    ]
    if head != latest:
        given.append(("head", head))
    if query.under is not None:
        given.append(("under", query.under))
    given += [("tag", tag) for tag in query.tag]
    return "?" + urlencode(given) if given else "?"


def _held(bench: Bench, value: JsonValue) -> str:
    if isinstance(value, str) and bench.rows.kind(value) is not None:
        return bench.title(value)
    return "—" if value is None else json.dumps(value)


def _drafted(bench: Bench, recipe: Recipe | None) -> dict[str, Any] | None:
    if recipe is None:
        return None
    chunks = {
        p: None if (d := getattr(recipe, p)) is None else _set(bench.store.get(d))
        for p in CHUNK_PARTS
    }
    into = chunks.pop("translations")
    return {
        "model": recipe.model,
        "chunks": chunks,
        "into": {} if into is None else into["into"],
        "texts": {p: list(t) for p, t in texts(recipe, bench.store.get).items()},
        "schemas": {
            p: BY_KIND[f"chunk.{p}"].model_json_schema()
            for p in CHUNK_PARTS
            if p != "translations"
        },
        "inserts": {
            p: sorted(INSERTS_BY_KIND[f"chunk.{p}"])
            for p in CHUNK_PARTS
            if f"chunk.{p}" in INSERTS_BY_KIND
        },
        "slots": {p: sorted(s) for p, s in SLOTS_BY_PURPOSE.items()},
        "tools": _tools(bench, recipe),
    }


def _facts(bench: Bench, model: str) -> dict[str, Any] | None:
    facts = bench.facts.about(model, bench.store.get)
    if facts is None:
        return None
    levels: dict[str, Any] = {}
    for level in ("default", *LEVELS):
        try:
            landed = facts.reasoning.landing(level)
        except Refused as e:
            levels[level] = {"refused": str(e)}
        else:
            levels[level] = {"lands": landed.level, "nearest": list(landed.nearest)}
    output: dict[str, Any] = {}
    for contract in ("native", "tool", "text"):
        match getattr(facts.output, contract):
            case Refusal(refused=refused):
                output[contract] = {"refused": refused}
            case ContractFact(note=note):
                output[contract] = {"note": note}
            case _:
                output[contract] = {}
    match facts.reasoning.budget:
        case Refusal(refused=refused):
            budget: bool | str = refused
        case None:
            budget = False
        case _:
            budget = True
    return {
        "levels": levels,
        "recommended": {
            level: values.model_dump(exclude_none=True)
            for level, values in facts.sampling.recommended.items()
        },
        "output": output,
        "answers": facts.output.default,
        "budget": budget,
    }


def _tool_choices(bench: Bench) -> list[dict[str, Any]]:
    mine = bench.person.login
    found: dict[str, schemas.Thread] = {}
    for t in sorted(api.threads(bench, "tool"), key=lambda t: t.owner != mine):
        if t.owner in {mine, ARCHIVE}:
            _ = found.setdefault(t.head.digest, t)
    tools = [(t, bench.store.get(t.head.digest)) for t in found.values()]
    return [
        {
            "digest": t.head.digest,
            "name": t.name or t.title,
            "description": getattr(tool, "description", ""),
        }
        for t, tool in tools
    ]


def _tools(bench: Bench, recipe: Recipe) -> dict[str, Any]:
    if recipe.toolset is None:
        return {}
    toolset = resolve(bench.store.get, recipe.toolset, Toolset)
    return {d: bench.store.get(d).model_dump(mode="json") for d in toolset.tools}


# Accommodating for the forms, which show a field that is set: a default left out is
# filled in again where it is read, to the same digest.
def _set(chunk: Component) -> dict[str, Any]:
    held = chunk.model_dump(mode="json")
    fields = type(chunk).model_fields
    return {
        k: v
        for k, v in held.items()
        if k == "kind"
        or getattr(chunk, k) != fields[k].get_default(call_default_factory=True)
    }


def _choices(bench: Bench, part: str, models: list[Handle]) -> list[schemas.Thread]:
    found = api.threads(bench, part)
    if part != "model":
        return found
    served = {m.weights for m in models}
    return [t for t in found if t.head.digest in served]
