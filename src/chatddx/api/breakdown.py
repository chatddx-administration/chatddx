from collections.abc import Mapping
from uuid import UUID

from fastapi import APIRouter, Depends

from chatddx.bench import Bench, NotFound
from chatddx.bench.breakdown import Estimate, Gathered, Point, Scored, View
from chatddx.factors.base import resolve
from chatddx.factors.scoring import Scorer
from chatddx.factors.select import field as field_of

from . import schemas
from .people import BenchDep
from .standing import baseline_cases
from .state import no_store
from .threads import edits, thread as threads_detail, threads

router = APIRouter(tags=["threads"])


@router.get("/threads/{thread}/breakdown", dependencies=[Depends(no_store)])
def breakdown(bench: BenchDep, thread: int) -> schemas.Broken:
    """How the configuration fared on the World's baseline cases: each baseline
    gathering in the order they ran, each view's estimate over its cases, each case's
    value and its difference from the gathering before, case by case; its means, how
    far its repeats were from it, the baseline cases it left unanswered, and its
    failed items, time and tokens; and the person's other configurations' latest
    baselines on the views they share. Costs a read of each of the person's runs and
    their scores, rows read before held."""
    tag = bench.inventory.baseline
    cases = baseline_cases(bench)
    if tag is None or not cases:
        raise NotFound("this World names no baseline cases")
    numbered = {e.id: n for n, e in enumerate(edits(bench, thread), start=1)}
    login = bench.person.login
    owned = {
        t.id: t
        for t in threads(bench, "configuration", purpose="generation", owner=login)
    }
    held = bench.breakdown(thread, cases, list(owned))
    views = list(held.views)

    def point(p: Point) -> schemas.BrokenPoint:
        return _point(p, numbered, views)

    shown = owned.get(thread) or threads_detail(bench, thread)
    return schemas.Broken(
        name=shown.name or shown.title,
        tag=tag,
        cases=len(cases),
        views=_views(bench, views),
        gatherings=[_gathered(g, numbered, views) for g in held.timeline],
        peers=[
            schemas.BrokenPeer(
                id=p.configuration,
                name=owned[p.configuration].name or owned[p.configuration].title,
                means=[p.point.means.get(v) if v in p.shared else None for v in views],
                point=point(p.point),
            )
            for p in held.peers
        ],
    )


@router.get("/gatherings/{started}", tags=["runs"], dependencies=[Depends(no_store)])
def gathering(bench: BenchDep, started: UUID) -> schemas.Gathering:
    """The baseline gathering begun by the run `started`: itself as its configuration's
    breakdown has it, the gathering before it, its runs, each a replicate or a repeat,
    and each case it sent or the World's baseline holds now, those first: the language
    it went in, whether it was answered, and alike to the letter by its repeat, and by
    view its replicate's value and score, its repeat's, and the gathering before's
    value. Costs what the configuration's breakdown costs."""
    tag = bench.inventory.baseline
    cases = baseline_cases(bench)
    if tag is None or not cases:
        raise NotFound("this World names no baseline cases")
    held = bench.baseline(started, cases)
    if held is None:
        raise NotFound(f"no baseline of yours begun by run {started}")
    thread = held.configuration
    numbered = {e.id: n for n, e in enumerate(edits(bench, thread), start=1)}
    shown = threads_detail(bench, thread)
    views = list(held.views)

    def by_view(found: Mapping[View, Scored]) -> list[schemas.GatheredValue | None]:
        return [
            None
            if (s := found.get(v)) is None
            else schemas.GatheredValue(value=s.value, score=s.score)
            for v in views
        ]

    return schemas.Gathering(
        configuration=thread,
        name=shown.name or shown.title,
        tag=tag,
        cases=len(cases),
        views=_views(bench, views),
        gathering=_gathered(held.gathered, numbered, views),
        before=None if held.before is None else _gathered(held.before, numbered, views),
        runs=[
            schemas.GatheredRun(run=r.run, language=r.language, repeat=r.repeat)
            for r in held.runs
        ],
        rows=[
            schemas.GatheredCase(
                case=c.case,
                language=c.language,
                answered=c.answered,
                alike=c.alike,
                replicate=by_view(c.replicate),
                repeat=by_view(c.repeat),
                before=[c.before.get(v) for v in views],
            )
            for c in held.cases
        ],
    )


def _point(
    p: Point, numbered: Mapping[int, int], views: list[View]
) -> schemas.BrokenPoint:
    return schemas.BrokenPoint(
        started=p.started,
        at=p.at,
        version=numbered.get(p.version, 0),
        means=[p.means.get(v) for v in views],
        spread=[p.spread.get(v) for v in views],
        alike=p.alike[0],
        compared=p.alike[1],
        languages=[
            schemas.BrokenLanguage(language=k, cases=n)
            for k, n in sorted(p.languages.items(), key=lambda kv: kv[0] or "")
        ],
        failed=p.failed,
        seconds=p.seconds,
        tokens=p.tokens,
        stale=p.stale,
        missing=p.missing,
    )


def _gathered(
    g: Gathered, numbered: Mapping[int, int], views: list[View]
) -> schemas.BrokenGathering:
    return schemas.BrokenGathering(
        digest=g.digest,
        point=_point(g.point, numbered, views),
        estimates=[_estimated(g.estimates.get(view)) for view in views],
        values=[sorted(g.values.get(view, {}).values()) for view in views],
        paired=[_estimated(g.paired.get(view)) for view in views],
    )


def _views(bench: Bench, views: list[View]) -> list[schemas.BrokenView]:
    titles = {t.head.digest: t.name or t.title for t in threads(bench, "scorer")}
    found: list[schemas.BrokenView] = []
    for digest, i in views:
        scorer = resolve(bench.store.get, digest, Scorer)
        label = bench.labels(digest).get(i, str(i))
        found.append(
            schemas.BrokenView(
                scorer=digest,
                view=i,
                label=f"{titles.get(digest, bench.title(digest))} › {label}",
                field=field_of(scorer.views[i].expectation),
            )
        )
    return found


def _estimated(e: Estimate | None) -> schemas.Estimated | None:
    return None if e is None else schemas.Estimated(mean=e.mean, half=e.half, n=e.n)
