import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from statistics import mean
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import JsonValue

from chatddx.api import (
    families as api_families,
    schemas,
    threads as api,
    world as api_world,
)
from chatddx.api.events import graded_of
from chatddx.api.state import refused
from chatddx.bench import Ambiguous, Bench, MovedOn, NotFound, Titled
from chatddx.bench.model import MODEL, PLACEHOLDERS
from chatddx.catalog import read as catalog_read, threads as catalog_threads
from chatddx.factors.base import Component, Finding, resolve
from chatddx.factors.request import Compilation, Skeleton
from chatddx.factors.scoring import Judge, Scorer, fill_text
from chatddx.factors.select import select
from chatddx.ledger import RunStarted
from chatddx.locale import tr
from chatddx.scorers.shipped import problems, unit_of

from .pages import BenchDep, own_first, page, refusal_of, within
from .titles import display_case

router = APIRouter()


def _judge_choices(bench: Bench) -> dict[str, list[dict[str, Any]]]:
    configurations = own_first(
        bench, api.threads(bench, "configuration", purpose="judge")
    )
    return {
        "judging": [
            {
                "digest": t.head.digest,
                "thread": t.id,
                "name": t.name or t.title,
                "owner": t.owner,
                "output_schema": resolve(
                    bench.store.get, t.head.digest, Skeleton
                ).output_schema,
                "weights": None
                if t.head.compilation is None
                else resolve(
                    bench.store.get, t.head.compilation, Compilation
                ).recipe.model,
            }
            for t in configurations
        ],
        "models": [
            {"name": h.name, "weights": h.weights}
            for h, at in bench.handles()
            if at is not None
        ],
    }


def code_of(bench: Bench, entry_point: str | None = None) -> schemas.ScorerCode:
    shipped = api_world.scorer_code(bench)
    if entry_point is None:
        return shipped[0]
    return {c.entry_point: c for c in shipped}[entry_point]


def unshipped(scorer: Scorer) -> str | None:
    if found := problems(scorer):
        return tr(
            "%(problems)s: create a new scorer to score with",
            problems="; ".join(found),
        )
    return None


def unit_in(bench: Bench, scorer: str, view: int) -> str:
    return unit_of(resolve(bench.store.get, scorer, Scorer), view)


def scorer_choices(
    bench: Bench, code: schemas.ScorerCode, judged: Iterable[str] = ()
) -> dict[str, Any]:
    return {
        "metrics": [m.model_dump(mode="json") for m in code.metrics],
        "outputs": _outputs(bench),
        "judges": _judges(bench),
        "titles": {j: bench.title(j) for j in judged},
        "me": bench.person.login,
        **_judge_choices(bench),
    }


def _judges(bench: Bench) -> list[dict[str, Any]]:
    return [
        _choice(bench, t, resolve(bench.store.get, t.head.digest, Judge))
        for t in own_first(bench, api.threads(bench, "judge"))
    ]


def _choice(bench: Bench, t: schemas.Thread, judge: Judge) -> dict[str, Any]:
    return {
        "digest": t.head.digest,
        "thread": t.id,
        "name": t.name or t.title,
        "owner": t.owner,
        "configuration": bench.title(judge.skeleton),
        "model": _model(bench, judge),
        "seeds": list(judge.seeds),
        "output_schema": resolve(
            bench.store.get, judge.skeleton, Skeleton
        ).output_schema,
    }


def _texts(bench: Bench, judge: Judge) -> dict[str, Any] | None:
    held = bench.holder(judge.skeleton)
    recipe = None if held is None else catalog_threads.recipe(bench.rows, held[0])
    if recipe is None:
        made = bench.store.compilations(judge.skeleton)
        recipe = made[0].recipe if made else None
    if recipe is None:
        return None
    return {
        "configuration": _holder(bench, judge.skeleton),
        "recipe": recipe.model_dump(mode="json"),
        "parts": {
            part: None if digest is None else _part(bench, digest)
            for part in ("instructions", "prompt", "output")
            for digest in [getattr(recipe, part)]
        },
    }


def _part(bench: Bench, digest: str) -> dict[str, Any]:
    given = {"digest": digest, "body": bench.store.get(digest).model_dump(mode="json")}
    held = _holder(bench, digest)
    if held is None:
        return {**given, "name": bench.title(digest), "thread": None}
    return {**given, **held, "language": api.thread(bench, held["thread"]).language}


def _holder(bench: Bench, digest: str) -> dict[str, Any] | None:
    held = bench.holder(digest)
    if held is None:
        return None
    edit, about = held
    return {
        "thread": edit.thread,
        "head": edit.id,
        "mine": about.owner == bench.person.id,
        "name": about.name or bench.title(digest),
    }


def _outputs(bench: Bench) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for t in api.threads(bench, "configuration", purpose="generation"):
        schema = resolve(bench.store.get, t.head.digest, Skeleton).output_schema
        held = found.setdefault(
            json.dumps(schema, sort_keys=True),
            {
                "title": schema.get("title") if isinstance(schema, dict) else None,
                "json_schema": schema,
                "by": [],
            },
        )
        held["by"].append(t.name or t.title)
    return list(found.values())


def checked(bench: Bench, held: Component) -> tuple[list[Finding], list[str]]:
    refused: list[str] = []
    if isinstance(held, Judge):
        try:
            _ = bench.judged(held)
        except ValueError as e:
            refused.append(refusal_of(e))
    try:
        return bench.check(held).findings, refused
    except (LookupError, ValueError) as e:
        return [], [*refused, refusal_of(e)]


@dataclass(frozen=True)
class _Asks:
    thread: int | None
    name: str
    latest: bool


@dataclass(frozen=True)
class _Viewed:
    label: str
    metric: str
    measures: str | None
    unit: str | None
    output: str
    split: str | None
    expectation: str
    params: dict[str, JsonValue]
    judge: _Asks | None


@dataclass(frozen=True)
class _Covered:
    expected: int
    choosing: list[schemas.Family]
    lacking: list[schemas.Family]


@dataclass(frozen=True)
class Fared:
    run: RunStarted
    titled: Titled
    means: list[float | None]


@dataclass(frozen=True)
class _ScorerShown:
    schema: str
    entry_point: str
    version: int
    unshipped: str | None
    views: list[_Viewed]
    resources: list[str]
    params: dict[str, JsonValue]
    reads: list[schemas.Thread]
    skips: list[schemas.Thread]
    covered: _Covered
    fared: list[Fared]


@dataclass(frozen=True)
class AskedBy:
    scorer: schemas.Thread
    label: str
    asks: str
    latest: bool
    at: int
    schema: str
    expectation: str

    @property
    def key(self) -> str:
        return f"{self.scorer.id}.{self.at}"


@dataclass(frozen=True)
class Read:
    by: AskedBy | None
    family: schemas.Family | None
    families: list[schemas.Family]
    data: JsonValue
    picked: list[JsonValue]


@dataclass
class _Judged:
    scorer: str
    label: str
    items: int = 0
    agree: int = 0
    short: int = 0
    values: list[float] = field(default_factory=list[float])

    @property
    def mean(self) -> float | None:
        return mean(self.values) if self.values else None


@dataclass(frozen=True)
class _Disagreed:
    run: UUID
    titled: Titled
    case: str
    replicate: int
    label: str
    seeds: list[float | None]


@dataclass(frozen=True)
class _JudgeShown:
    configuration: _Asks
    model: str
    seeds: list[int]
    fill: str
    sent: str | None
    unsent: str | None
    asked_by: list[AskedBy]
    behind: list[tuple[schemas.Thread, list[str]]]
    read: Read
    asked: dict[str, JsonValue]
    judged: list[_Judged]
    disagreed: list[_Disagreed]
    editing: dict[str, Any]


@router.get("/scoring")
def scorings(request: Request, bench: BenchDep) -> Response:
    scorers, judges = _drawn(bench)
    first = next((t for _, held in scorers for t in held), None)
    if first is None and judges:
        first = judges[0][0]
    if first is not None:
        return RedirectResponse(f"/scoring/{first.id}", 303)
    return page(request, "scoring.html", person=bench.person, shown=None)


@router.get("/scoring/{thread}")
def scoring(
    request: Request,
    bench: BenchDep,
    thread: int,
    view: str | None = None,
    family: int | None = None,
) -> Response:
    shown = api.thread(bench, thread)
    if shown.kind not in ("scorer", "judge"):
        raise NotFound.of(
            "no scorer or judge %(thread)s for %(login)s",
            thread=thread,
            login=bench.person.login,
        )
    held = bench.store.get(shown.head.digest)
    gone = unshipped(held) if isinstance(held, Scorer) else None
    found, refused = ([], []) if gone else checked(bench, held)
    scorers, judges = _drawn(bench)
    judge = (
        _judge(bench, shown, held, view, family) if isinstance(held, Judge) else None
    )
    mine = shown.owner == bench.person.login and not shown.deleted
    return page(
        request,
        "scoring.html",
        person=bench.person,
        shown=shown,
        proposal=api.proposal(bench, thread) if mine else None,
        scorers=scorers,
        judges=judges,
        scorer=_scorer(bench, held, gone) if isinstance(held, Scorer) else None,
        judge=judge,
        findings=found,
        refused=refused,
        props=None if judge is None else judge.editing,
        island=None if judge is None else "scoring",
    )


def _drawn(
    bench: Bench,
) -> tuple[list[tuple[str, list[schemas.Thread]]], list[tuple[schemas.Thread, str]]]:
    by: dict[str, list[schemas.Thread]] = {}
    for t in own_first(bench, api.threads(bench, "scorer")):
        schema = resolve(bench.store.get, t.head.digest, Scorer).expectation_schema
        by.setdefault(bench.title(schema), []).append(t)
    judges = [
        (t, _model(bench, resolve(bench.store.get, t.head.digest, Judge)))
        for t in own_first(bench, api.threads(bench, "judge"))
    ]
    return sorted(by.items()), judges


def _model(bench: Bench, judge: Judge) -> str:
    return bench.handle(judge.model).name


def _asks(bench: Bench, digest: str) -> _Asks:
    held = bench.holder(digest)
    if held is None:
        return _Asks(None, bench.title(digest), True)
    edit, about = held
    latest = catalog_threads.head(bench.rows, edit.thread).id == edit.id
    return _Asks(edit.thread, about.name or bench.title(digest), latest)


def _scorer(bench: Bench, scorer: Scorer, gone: str | None) -> _ScorerShown:
    labels = bench.labels(scorer.digest)
    code = None if gone else code_of(bench, scorer.entry_point)
    metrics = {} if code is None else {m.name: m for m in code.metrics}
    views = [
        _Viewed(
            label=labels.get(i, tr("view %(n)s", n=i)),
            metric=v.metric,
            measures=None if (m := metrics.get(v.metric)) is None else m.measures,
            unit=None if m is None else m.unit,
            output=v.output,
            split=v.split,
            expectation=v.expectation,
            params=dict(v.params),
            judge=None if v.judge is None else _asks(bench, v.judge),
        )
        for i, v in enumerate(scorer.views)
    ]
    reads: list[schemas.Thread] = []
    skips: list[schemas.Thread] = []
    for t in own_first(
        bench, api.threads(bench, "configuration", purpose="generation")
    ):
        schema = resolve(bench.store.get, t.head.digest, Skeleton).output_schema
        offered = all(v.offered_by(schema) for v in scorer.views)
        (reads if offered else skips).append(t)
    return _ScorerShown(
        schema=bench.title(scorer.expectation_schema),
        entry_point=scorer.entry_point,
        version=scorer.version,
        unshipped=gone,
        views=views,
        resources=list(scorer.resources),
        params=dict(scorer.params),
        reads=reads,
        skips=skips,
        covered=_covered(bench, scorer.expectation_schema),
        fared=_fared(bench, scorer.digest),
    )


def _covered(bench: Bench, schema: str) -> _Covered:
    expected = 0
    choosing: list[schemas.Family] = []
    lacking: list[schemas.Family] = []
    for f in api_families.families(bench):
        try:
            held = bench.expectation(f.case, schema)
        except Ambiguous:
            choosing.append(f)
            continue
        if held is None:
            lacking.append(f)
        else:
            expected += 1
    return _Covered(expected, choosing, lacking)


def _fared(bench: Bench, scorer: str) -> list[Fared]:
    found: list[Fared] = []
    for started in bench.runs(scored_by=scorer):
        graded = next(
            (g for g in bench.scores_of(started) if g.scorer.digest == scorer), None
        )
        if graded is not None:
            found.append(Fared(started, bench.titled(started), graded_of(graded).means))
    return found


def _judge(
    bench: Bench,
    shown: schemas.ThreadDetail,
    judge: Judge,
    view: str | None,
    family: int | None,
) -> _JudgeShown:
    versions = {e.digest for e in api.edits(bench, shown.id)}
    lineage = _lineage(bench, shown)
    asked_by: list[AskedBy] = []
    for t in own_first(bench, api.threads(bench, "scorer")):
        scorer = resolve(bench.store.get, t.head.digest, Scorer)
        labels = bench.labels(scorer.digest)
        asked_by.extend(
            AskedBy(
                t,
                labels.get(i, tr("view %(n)s", n=i)),
                lineage[v.judge],
                v.judge == shown.head.digest,
                i,
                scorer.expectation_schema,
                v.expectation,
            )
            for i, v in enumerate(scorer.views)
            if v.judge in lineage
        )
    behind: dict[int, tuple[schemas.Thread, list[str]]] = {}
    for a in asked_by:
        if not a.latest:
            behind.setdefault(a.scorer.id, (a.scorer, []))[1].append(a.label)
    read = _read(bench, asked_by, view, family)
    fills = dict(PLACEHOLDERS)
    if read.picked:
        fills["expectation"] = fill_text(judge.fill, read.picked)
    sent, unsent = None, None
    try:
        sent = bench.judged(judge).name
    except (LookupError, ValueError) as e:
        unsent = refusal_of(e)
    skeleton = resolve(bench.store.get, judge.skeleton, Skeleton)
    judged, disagreed = _verdicts(bench, versions)
    return _JudgeShown(
        configuration=_asks(bench, judge.skeleton),
        model=_model(bench, judge),
        seeds=list(judge.seeds),
        fill=judge.fill,
        sent=sent,
        unsent=unsent,
        asked_by=asked_by,
        behind=list(behind.values()),
        read=read,
        asked=skeleton.render(
            model=MODEL, seed=judge.seeds[0], fills=fills, return_token_ids=False
        ),
        judged=judged,
        disagreed=disagreed,
        editing={
            "judge": {
                **_choice(bench, shown, judge),
                "head": shown.head.id,
                "body": judge.model_dump(mode="json"),
                "texts": _texts(bench, judge),
            },
            "expectation": "" if read.by is None else read.by.expectation,
            "data": read.data,
            "me": bench.person.login,
        },
    )


def _lineage(bench: Bench, shown: schemas.ThreadDetail) -> dict[str, str]:
    edits = api.edits(bench, shown.id)
    last = max(e.version for e in edits)
    found = {
        e.digest: tr("version %(at)s of %(last)s", at=e.version, last=last)
        for e in edits
    }
    found[shown.head.digest] = tr("its latest version")
    origin = shown.forked_from
    while origin is not None and (edit := bench.rows.edit(origin)) is not None:
        try:
            above = api.thread(bench, edit.thread)
        except LookupError:
            break
        named = (above.owner + "/" if above.owner else "") + (above.name or above.title)
        for e in api.edits(bench, above.id):
            forked = tr("%(thread)s, which it is forked from", thread=named)
            _ = found.setdefault(e.digest, forked)
        origin = above.forked_from
    return found


@router.post("/scoring/{thread}/follow")
def following(
    bench: BenchDep,
    thread: int,
    scorer: Annotated[int, Form()],
    head: Annotated[int, Form()],
) -> Response:
    shown = api.thread(bench, thread)
    if shown.kind != "judge":
        raise NotFound.of(
            "no judge %(thread)s for %(login)s", thread=thread, login=bench.person.login
        )
    lineage = _lineage(bench, shown)
    edit, about = bench.thread(scorer, "scorer")
    held = resolve(bench.store.get, edit.digest, Scorer)
    views = [
        v.model_dump(mode="json")
        | ({"judge": shown.head.digest} if v.judge in lineage else {})
        for v in held.views
    ]
    followed = Scorer.model_validate(held.model_dump(mode="json") | {"views": views})
    back = within(f"/scoring/{thread}")
    if followed.digest == held.digest:
        return RedirectResponse(back, 303)
    labels = catalog_read.labels(bench.rows, edit.id)
    with refused():
        if edit.id != head:
            raise MovedOn.of(
                "scorer %(scorer)s has a newer version: look at it again", scorer=scorer
            )
        if about.owner == bench.person.id:
            _ = bench.edit(scorer, head, followed, labels=labels)
        else:
            name = about.name or bench.title(edit.digest)
            _ = bench.fork(scorer, name, followed, labels=labels)
    return RedirectResponse(back, 303)


def _read(
    bench: Bench, asked_by: list[AskedBy], view: str | None, family: int | None
) -> Read:
    by = next((a for a in asked_by if view in (None, a.key)), None)
    if by is None:
        if view is not None:
            raise NotFound.of("no view %(view)s asks this judge", view=view)
        return Read(None, None, [], None, [])
    expected: list[tuple[schemas.Family, JsonValue]] = []
    for f in api_families.families(bench):
        try:
            held = bench.expectation(f.case, by.schema)
        except Ambiguous:
            continue
        if held is not None:
            expected.append((f, held.data))
    found = next(((f, d) for f, d in expected if f.id == family), None)
    found = found or next(
        ((f, d) for f, d in expected if select(d, by.expectation)), None
    )
    found = found or next(iter(expected), None)
    families = [f for f, _ in expected]
    if found is None:
        return Read(by, None, families, None, [])
    return Read(by, found[0], families, found[1], select(found[1], by.expectation))


def _verdicts(
    bench: Bench, versions: set[str]
) -> tuple[list[_Judged], list[_Disagreed]]:
    runs = {r.run: r for d in versions for r in bench.runs(scored_by=d)}
    tallied: dict[tuple[str, str], _Judged] = {}
    disagreed: list[_Disagreed] = []
    for started in runs.values():
        for graded in bench.scores_of(started):
            if graded.score is None:
                continue
            for item in graded.score.items:
                if graded.scorer.views[item.view].judge not in versions:
                    continue
                if not item.judge_calls:
                    continue
                label = graded.label(item.view)
                held = tallied.setdefault(
                    (graded.name, label), _Judged(graded.name, label)
                )
                seeds = _seeds(item.detail)
                given = {s for s in seeds if s is not None}
                held.items += 1
                held.agree += len(given) == 1 and None not in seeds
                held.short += None in seeds
                if item.value is not None:
                    held.values.append(item.value)
                if len(given) > 1:
                    disagreed.append(
                        _Disagreed(
                            run=started.run,
                            titled=bench.titled(started),
                            case=display_case(bench.titled_case(item.key.case)),
                            replicate=item.key.replicate,
                            label=label,
                            seeds=seeds,
                        )
                    )
    return sorted(tallied.values(), key=lambda j: (j.scorer, j.label)), disagreed


def _seeds(detail: JsonValue) -> list[float | None]:
    held = detail.get("seeds") if isinstance(detail, dict) else None
    if not isinstance(held, list):
        return []
    return [float(s) if isinstance(s, int | float) else None for s in held]
