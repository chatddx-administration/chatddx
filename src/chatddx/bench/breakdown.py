import math
from collections import Counter
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import mean, stdev
from uuid import UUID

from chatddx.factors.base import resolve
from chatddx.factors.gatherer import gather
from chatddx.factors.gathering import BASELINE, Center
from chatddx.factors.request import Skeleton

from .observed import Observed, Ran, observed
from .seen import Seen

type View = tuple[str, int]


@dataclass(frozen=True)
class Estimate:
    """A mean of `n` values, each a case's, with the half-width of its 95% interval,
    None for fewer than two."""

    mean: float
    half: float | None
    n: int


@dataclass(frozen=True)
class Point:
    """One baseline gathering of a configuration: `means` over its replicates alone,
    `spread` and `alike` its repeats against them, `missing` the baseline cases none
    of its replicates answered without failing."""

    started: UUID
    at: datetime
    version: int
    means: dict[View, float]
    spread: dict[View, float]
    alike: tuple[int, int]
    languages: dict[str | None, int]
    failed: float
    seconds: float
    tokens: float | None
    stale: bool
    missing: int


@dataclass(frozen=True)
class Gathered:
    """One baseline gathering of the configuration, `digest` the skeleton it ran:
    each view's estimate over its cases, each case's value, and its mean difference
    from the gathering before it on the cases both sent, case by case."""

    digest: str
    point: Point
    estimates: dict[View, Estimate]
    values: dict[View, dict[str, float]]
    paired: dict[View, Estimate]


@dataclass(frozen=True)
class Peer:
    """Another configuration's latest baseline gathering, on the views it shares with
    the one broken down."""

    configuration: int
    point: Point
    shared: tuple[View, ...]


@dataclass(frozen=True)
class Breakdown:
    """How a configuration fared on the baseline cases: the views its skeleton offers,
    its baseline gatherings in the order they ran, a version once for each time it
    ran, and its peers among the configurations given."""

    views: tuple[View, ...]
    timeline: tuple[Gathered, ...]
    peers: tuple[Peer, ...]


def breakdown(
    seen: Seen, thread: int, cases: Collection[str], peers: Collection[int] = ()
) -> Breakdown:
    """How the configuration fared on the cases, as the baseline gatherings of its
    versions and of the peers' latest have it. A baseline is a start of runs of none
    but the cases on one seed each, as Run starts one, of no parts replaced. Costs what
    `observed` costs for each of the person's runs, cached rows costing nothing, and
    each configuration's head resolved."""
    within = set(cases)
    offered = _offered(seen)
    views = offered(_head(seen, thread))
    starts = _baselines(seen, observed(seen, seen.runs()), within)
    mine = sorted(
        (p for p in starts if p.ran[0].configuration == thread),
        key=lambda s: s.point.at,
    )
    timeline: list[Gathered] = []
    for s in mine:
        digest = s.ran[0].digest
        assert digest is not None
        values = {
            v: {case: mean(xs) for case, xs in by.items()}
            for v, by in _by_case([s]).items()
            if v in views
        }
        before = timeline[-1] if timeline else None
        timeline.append(
            Gathered(
                digest=digest,
                point=s.point,
                estimates={
                    v: e
                    for v in views
                    if (e := estimate(list(values.get(v, {}).values())))
                },
                values=values,
                paired={} if before is None else _paired(views, before.values, values),
            )
        )
    found: list[Peer] = []
    for other in peers:
        if other == thread:
            continue
        theirs = [s for s in starts if s.ran[0].configuration == other]
        shared = tuple(v for v in offered(_head(seen, other)) if v in views)
        if theirs and shared:
            latest = max(theirs, key=lambda s: s.ran[0].at)
            found.append(Peer(other, latest.point, shared))
    return Breakdown(views, tuple(timeline), tuple(found))


@dataclass(frozen=True)
class Scored:
    """A case's value under a view, with the score it is read from."""

    value: float
    score: UUID


@dataclass(frozen=True)
class GatheredCase:
    """A baseline case in one gathering: the language it went in, whether its
    replicate answered without failing, whether its repeat answered alike to the
    letter, None where either said nothing, and by view its replicate's value, its
    repeat's and the gathering before's."""

    case: str
    language: str | None
    answered: bool
    alike: bool | None
    replicate: dict[View, Scored]
    repeat: dict[View, Scored]
    before: dict[View, float]


@dataclass(frozen=True)
class GatheredRun:
    run: UUID
    language: str | None
    repeat: bool


@dataclass(frozen=True)
class Baseline:
    """One baseline gathering of a configuration as a page shows it: itself as its
    breakdown has it, the one before it, its runs, and each case it sent or the
    baseline holds now, those the baseline holds first."""

    configuration: int
    views: tuple[View, ...]
    gathered: Gathered
    before: Gathered | None
    runs: tuple[GatheredRun, ...]
    cases: tuple[GatheredCase, ...]


def baseline(seen: Seen, started: UUID, cases: Collection[str]) -> Baseline | None:
    """The person's baseline gathering begun by `started` on the cases, with the
    configuration's gathering before it, None if it is no such gathering. Costs what
    `breakdown` costs."""
    within = set(cases)
    starts = _baselines(seen, observed(seen, seen.runs()), within)
    found = next((s for s in starts if s.point.started == started), None)
    if found is None or (thread := found.ran[0].configuration) is None:
        return None
    held = breakdown(seen, thread, cases)
    at = next(i for i, g in enumerate(held.timeline) if g.point.started == started)
    before = held.timeline[at - 1] if at else None
    runs = sorted(
        [GatheredRun(o.ran.run, o.ran.language, False) for o in found.replicates]
        + [
            GatheredRun(o.ran.run, o.ran.language, True) for o in found.repeats.values()
        ],
        key=lambda r: (r.language or "", r.repeat),
    )
    rows: list[GatheredCase] = []
    sent = {i.case for o in found.replicates for i in o.ran.items}
    for case in sorted(sent | within):
        replicate = next((o for o in found.replicates if case in o.ran.cases), None)
        repeat = None if replicate is None else found.repeats.get(replicate.ran.run)
        said = None if replicate is None else _said(replicate, case)
        again = None if repeat is None else _said(repeat, case)
        rows.append(
            GatheredCase(
                case=case,
                language=None if replicate is None else replicate.ran.language,
                answered=replicate is not None
                and any(i.case == case and not i.failed for i in replicate.ran.items),
                alike=None if said is None or again is None else said == again,
                replicate={} if replicate is None else _scored(replicate, case),
                repeat={} if repeat is None else _scored(repeat, case),
                before={}
                if before is None
                else {v: by[case] for v, by in before.values.items() if case in by},
            )
        )
    return Baseline(
        thread,
        held.views,
        held.timeline[at],
        before,
        tuple(runs),
        tuple(sorted(rows, key=lambda r: r.case not in within)),
    )


def _said(o: Observed, case: str) -> str | None:
    return next((i.said for i in o.ran.items if i.case == case), None)


def _scored(o: Observed, case: str) -> dict[View, Scored]:
    return {
        (s.scorer, view): Scored(value, s.score)
        for s in o.scores
        for c, replicate, view, value in s.values
        if c == case and replicate == 0 and value is not None
    }


@dataclass(frozen=True)
class _Start:
    ran: tuple[Ran, ...]
    replicates: tuple[Observed, ...]
    repeats: dict[UUID, Observed]
    point: Point


def _head(seen: Seen, thread: int) -> Skeleton:
    edit, _ = seen.thread(thread, "configuration")
    return resolve(seen.store.get, edit.digest, Skeleton)


def _offered(seen: Seen) -> Callable[[Skeleton], tuple[View, ...]]:
    scorers = [s for _, _, s in seen.scorers()]

    def offered(skeleton: Skeleton) -> tuple[View, ...]:
        return tuple(
            (s.digest, i)
            for s in scorers
            for i, v in enumerate(s.views)
            if v.offered_by(skeleton.output_schema)
        )

    return offered


def _baselines(seen: Seen, found: Sequence[Observed], within: set[str]) -> list[_Start]:
    starts: dict[tuple[int, UUID], list[Observed]] = {}
    for o in found:
        r = o.ran
        if r.configuration is None or r.replaced:
            continue
        starts.setdefault((r.configuration, r.started_with), []).append(o)
    made: list[_Start] = []
    for each in starts.values():
        if not all(set(o.ran.cases) <= within and len(o.ran.seeds) == 1 for o in each):
            continue
        by_run = {o.ran.run: o for o in each}
        held = gather(
            Center(component=each[0].ran.skeleton),
            BASELINE,
            [
                (o.ran.skeleton, o.ran.run, o.ran.trial)
                for o in sorted(each, key=lambda o: o.ran.at)
            ],
            seen.store.get,
        )
        if held is None:
            continue
        groups = held.groups()
        replicates = tuple(
            by_run[g["replicates"].run] for g in groups if "replicates" in g
        )
        repeats = {
            by_run[g["replicates"].run].ran.run: by_run[g["repeat"].run]
            for g in groups
            if "replicates" in g and "repeat" in g
        }
        if not replicates:
            continue
        made.append(
            _Start(
                tuple(o.ran for o in each),
                replicates,
                repeats,
                _point(each, replicates, repeats, within),
            )
        )
    return made


def _point(
    each: list[Observed],
    replicates: tuple[Observed, ...],
    repeats: dict[UUID, Observed],
    within: set[str],
) -> Point:
    first = min((o.ran for o in each), key=lambda r: r.at)
    means: dict[View, list[float]] = {}
    spread: dict[View, list[float]] = {}
    alike = [0, 0]
    languages: Counter[str | None] = Counter()
    for o in replicates:
        languages.update({o.ran.language: len(o.ran.cases)})
        mine = _values(o)
        for (_, view), value in mine.items():
            means.setdefault(view, []).append(value)
        repeat = repeats.get(o.ran.run)
        if repeat is None:
            continue
        theirs = _values(repeat)
        for at, value in mine.items():
            if at in theirs:
                spread.setdefault(at[1], []).append(abs(value - theirs[at]))
        said = {i.case: i.said for i in repeat.ran.items}
        for i in o.ran.items:
            if i.said is not None and said.get(i.case) is not None:
                alike[1] += 1
                alike[0] += i.said == said[i.case]
    items = [i for o in each for i in o.ran.items]
    tokens = [i.tokens for i in items if i.tokens is not None]
    return Point(
        started=first.started_with,
        at=first.at,
        version=first.version or 0,
        means={v: mean(xs) for v, xs in means.items()},
        spread={v: mean(xs) for v, xs in spread.items()},
        alike=(alike[0], alike[1]),
        languages=dict(languages),
        failed=sum(i.failed for i in items) / len(items) if items else 0.0,
        seconds=mean(i.seconds for i in items) if items else 0.0,
        tokens=mean(tokens) if tokens else None,
        stale=any(o.unscored for o in each),
        missing=len(
            within - {i.case for o in replicates for i in o.ran.items if not i.failed}
        ),
    )


def _values(o: Observed) -> dict[tuple[str, View], float]:
    return {
        (case, (s.scorer, view)): value
        for s in o.scores
        for case, replicate, view, value in s.values
        if replicate == 0 and value is not None
    }


def _by_case(starts: Sequence[_Start]) -> dict[View, dict[str, list[float]]]:
    found: dict[View, dict[str, list[float]]] = {}
    for s in starts:
        for o in s.replicates:
            for (case, view), value in _values(o).items():
                found.setdefault(view, {}).setdefault(case, []).append(value)
    return found


def _paired(
    views: Sequence[View],
    before: dict[View, dict[str, float]],
    after: dict[View, dict[str, float]],
) -> dict[View, Estimate]:
    found: dict[View, Estimate] = {}
    for v in views:
        then, now = before.get(v, {}), after.get(v, {})
        diffs = [now[c] - then[c] for c in now if c in then]
        if (e := estimate(diffs)) is not None:
            found[v] = e
    return found


def estimate(values: Sequence[float]) -> Estimate | None:
    """The mean of values, one a case, with Student's t interval over them: a case's
    replicates aren't independent draws of how a configuration fares, so they are
    averaged before they get here. None for none."""
    if not values:
        return None
    if len(values) < 2:
        return Estimate(values[0], None, 1)
    half = t975(len(values) - 1) * stdev(values) / math.sqrt(len(values))
    return Estimate(mean(values), half, len(values))


_T975 = tuple(
    t
    for row in (
        (12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228),
        (2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086),
        (2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042),
    )
    for t in row
)


def t975(df: int) -> float:
    """Student's t at 0.975 for `df` degrees of freedom: tabled to 30, then by the
    Cornish-Fisher expansion, within 0.001."""
    if df < 1:
        raise ValueError(f"df must be at least 1, not {df}")
    if df <= len(_T975):
        return _T975[df - 1]
    z = 1.959964
    return z + (z**3 + z) / (4 * df) + (5 * z**5 + 16 * z**3 + 3 * z) / (96 * df**2)
