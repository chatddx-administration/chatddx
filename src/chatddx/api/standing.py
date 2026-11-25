from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from chatddx.bench import Bench, NotFound
from chatddx.bench.seen import trial
from chatddx.factors.base import Invalid, resolve
from chatddx.factors.gatherer import gather
from chatddx.factors.gathering import Center, Seeding
from chatddx.factors.request import untranslated
from chatddx.factors.scoring import Scorer
from chatddx.factors.trial import Trial
from chatddx.ledger import RunStarted
from chatddx.runner import Refused
from chatddx.runner.gate import bar
from chatddx.store import Queue

from . import schemas
from .threads import threads

OPEN = ("queued", "under way")

type Why = Literal[
    "under_way",
    "outdated",
    "untranslated",
    "refused",
    "no_runs",
    "not_whole",
    "changed",
    "halted",
    "unfinished",
    "unscored",
]

type Seeds = Mapping[str, tuple[int, ...]]


@dataclass(frozen=True)
class Behind:
    """Why a configuration's latest gathering on the cases isn't whole in its shape as
    things are now, and what Run does about it: runs it again on `rerun`'s seeds,
    drawing those it doesn't hold, resumes `resume` and scores `rescore` again."""

    why: Why
    refusal: Exception | None = None
    language: str | None = None
    rerun: Seeds | None = None
    resume: tuple[UUID, ...] = ()
    rescore: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class Standing:
    configuration: schemas.Thread
    runs: list[RunStarted]
    behind: list[Behind] = field(default_factory=list[Behind])
    version: int | None = None


def configurations(bench: Bench) -> list[schemas.Thread]:
    """The person's own configurations that generate, by name."""
    found = threads(bench, "configuration", owner=bench.person.login)
    return sorted(found, key=lambda t: t.name or t.title)


def baseline_cases(bench: Bench) -> list[str]:
    """The World's baseline cases the person sees: the bare case of each family tagged
    with its baseline tag, none when it names none. Reads the person's families."""
    tag = bench.inventory.baseline
    return [] if tag is None else [f.case for f in bench.families([tag])]


def against(
    bench: Bench, schema: str | None, marked: bool
) -> Callable[[RunStarted], list[str]]:
    """What a review's gathering is to be scored by: of the scorers under the schema,
    those a finished run isn't scored by as things are now, if `marked`, else none."""
    return (lambda r: stale(bench, r, schema)) if marked else (lambda _: [])


def standing(
    bench: Bench,
    configurations: Sequence[schemas.Thread],
    cases: Sequence[str],
    seedings: tuple[Seeding, ...],
    left: Callable[[RunStarted], list[str]],
    at: int | None = None,
) -> list[Standing]:
    """How each configuration's latest gathering on the cases stands in the seedings'
    shape, as `bench.latest_starts` has it: under way, or what keeps it from being
    whole, in each language the cases are sent in and scored by what `left` gives, as
    the cases and the configuration are now, at its version `at` when given, else at
    its head. A case that can't be sent in its language keeps the whole gathering from
    running.

    Costs the person's runs read with their catalog rows and trials, their places in
    the queue, and, for each configuration, the trial of each language built twice and
    gated, and its finished runs given to `left`."""
    compiled = None
    if at is not None:
        edit = bench.rows.edit(at)
        if edit is None:
            raise NotFound(f"no version {at}")
        compiled = {edit.thread: edit.digest}
    latest = bench.latest_starts(cases, seedings, compiled)
    ids = [r.run for runs in latest.values() for r in runs]
    placed = Queue(bench.conn).placed(ids)
    finished = bench.store.finished(ids)

    def status(run: UUID) -> str | None:
        held = placed.get(run)
        return None if held is None else held.job.status

    found: list[Standing] = []
    for t in configurations:
        runs = latest.get(t.id, [])
        behind = _behind(bench, t, at, cases, seedings, runs, status, finished, left)
        found.append(Standing(t, runs, behind, at))
    return found


def _behind(
    bench: Bench,
    t: schemas.Thread,
    at: int | None,
    cases: Sequence[str],
    seedings: tuple[Seeding, ...],
    runs: list[RunStarted],
    status: Callable[[UUID], str | None],
    finished: set[UUID],
    left: Callable[[RunStarted], list[str]],
) -> list[Behind]:
    if any(status(r.run) in OPEN for r in runs):
        return [Behind("under_way")]
    if t.outdated:
        return [Behind("outdated")]
    try:
        variation = bench.variation(t.id, {}, at)
        endpoint = bench.at(variation)
    except (Invalid, NotFound) as e:
        return [Behind("refused", refusal=e)]
    carried = bench.languages(variation, cases)
    recipe = variation.varied
    for each in carried:
        partly = (
            each.skeleton is None
            and each.language is not None
            and recipe is not None
            and bool(untranslated(recipe, bench.store.get, each.language))
        )
        if each.untranslated or partly:
            return [Behind("untranslated", language=str(each.language))]
        if each.skeleton is None:
            return [Behind("refused", refusal=Invalid(each.refused or ""))]
    sent = [(c, c.skeleton) for c in carried if c.skeleton is not None]
    for each, skeleton in sent:
        registry, made = trial(bench, skeleton, endpoint.engine, each.cases, (0,))
        try:
            bar(bench.inventory, registry.get, endpoint.name, made)
        except Refused as e:
            return [Behind("refused", refusal=e)]
    if not runs:
        return [Behind("no_runs", rerun={})]
    get = bench.store.get
    held = gather(
        Center(component=t.head.digest),
        seedings,
        [(resolve(get, r.trial, Trial).skeleton, r.run, r.trial) for r in runs],
        get,
    )
    groups = [] if held is None else held.groups()
    seeds: Seeds = (
        {s: resolve(get, g.trial, Trial).seeds for s, g in groups[0].items()}
        if groups
        else {}
    )
    whole = len(groups) == len(sent) and all(len(g) == len(seedings) for g in groups)
    if not whole or len(runs) > len(seedings) * len(groups):
        return [Behind("not_whole", rerun=seeds)]
    head = seedings[0].name
    now = {
        trial(
            bench,
            skeleton,
            endpoint.engine,
            each.cases,
            seeds[head],
            bench.cleanup(each.cases),
        )[1].digest
        for each, skeleton in sent
    }
    if {g[head].trial for g in groups} != now:
        return [Behind("changed", rerun=seeds)]
    gathered = [g.run for group in groups for g in group.values()]
    if any(status(r) == "stopped" for r in gathered):
        return [Behind("halted", rerun=seeds)]
    found: list[Behind] = []
    if unsent := tuple(r for r in gathered if r not in finished):
        found.append(Behind("unfinished", resume=unsent))
    if unscored := tuple(r.run for r in runs if r.run in finished and left(r)):
        found.append(Behind("unscored", rescore=unscored))
    return found


def stale(bench: Bench, run: RunStarted, schema: str | None) -> list[str]:
    """The scorers under the schema that the run, finished, isn't scored by as things
    are now, by digest. Costs what `bench.unscored` costs."""
    return [
        s
        for s in bench.unscored(run)
        if resolve(bench.store.get, s, Scorer).expectation_schema == schema
    ]
