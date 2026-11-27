from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from chatddx import settings
from chatddx.catalog import Entry, EntryField, Subject, read, titles
from chatddx.catalog.families import family_of
from chatddx.factors.base import Invalid, resolve
from chatddx.factors.bundle import Registry
from chatddx.factors.cases import CleanupOp
from chatddx.factors.engine import model_of
from chatddx.factors.request import RECIPE_PARTS, Skeleton
from chatddx.factors.trial import CanarySet, Execution, Order, Trial
from chatddx.ledger import RunStarted
from chatddx.ledger.run import PHASES, Phase
from chatddx.runner import STOPPED, Grading, Halt, Refused, Runner, Running, ScoreEvent
from chatddx.store import Job, Queue

from .configurations import keep_compilation
from .errors import NotFound, OverQuota
from .model import Carried, Graded, Started
from .seen import Seen, labels_of, scoring, trial
from .variation import TriedVariation

REFUSALS = (LookupError, TypeError, ValueError, NotImplementedError, Refused)


def start(
    seen: Seen,
    variation: TriedVariation,
    endpoint: str | None,
    cases: list[str],
    seeds: Sequence[int],
    cleanup: Sequence[CleanupOp] | None = None,
    execution: Execution | None = None,
    canaries: str | None = None,
    joining: UUID | None = None,
) -> Started:
    """Begins a run for each language the cases are sent in, and sends nothing; given
    `joining`, the first run of an earlier start, its runs are listed as of that start.

    Compiles the variation into each language, and stores each run's trial, start record
    and entries, and the compilations of what it begins, in one transaction, which holds
    while the gate confirms the endpoint with a request to it for each run.

    Heads-up: the gate's `Refused` passes through.
    """
    if seen.skeleton(variation).purpose == "judge":
        raise ValueError(
            f"{variation.label} is a judge configuration: a judge is asked as runs are "
            + "scored, and isn't run on cases"
        )
    seen_cases = {c for f in seen.families() for c in f.cases}
    if missing := [c for c in cases if c not in seen_cases]:
        raise NotFound(f"no case {missing[0]} for {seen.person.login}")
    carried = seen.languages(variation, cases)
    sent = [c for c in carried if c.skeleton is not None]
    left_out = [c for c in carried if c.skeleton is None]
    if not sent and left_out and all(c.untranslated for c in left_out):
        raise Invalid.of(
            "%(name)s has no translation into %(languages)s",
            name=variation.label,
            languages=", ".join(str(c.language) for c in left_out),
        )
    if not sent:
        raise Invalid.of(
            "no case can be sent: %(refused)s",
            refused="; ".join(c.refused or "" for c in left_out),
        )
    at = seen.at(variation, endpoint)
    canaries = canaries or at.spec.canaries
    check_quota(seen, [len(c.cases) * len(seeds) for c in sent])
    said = _varying(
        variation.configuration.id,
        {p: variation.parts[p][0] for p in RECIPE_PARTS if p in variation.parts},
    )
    runs: list[tuple[Carried, Running]] = []
    # Policy: one transaction, so that a run the gate refuses leaves none of the start's
    # begun.
    with seen.conn.transaction():
        for each in sent:
            assert each.skeleton is not None
            first = joining or (runs[0][1].run if runs else None)
            with_first = [] if first is None else [Entry.started_with(first)]
            running = _begun(
                seen,
                each.skeleton,
                at.name,
                at.engine,
                each.cases,
                seeds,
                variation.label,
                [*said, *with_first],
                cleanup=seen.cleanup(each.cases) if cleanup is None else tuple(cleanup),
                execution=execution or at.spec.execution,
                canaries=None
                if canaries is None
                else resolve(seen.store.get, canaries, CanarySet),
            )
            runs.append((each, running))
            if each.translated:
                _ = keep_compilation(seen, variation, each.language)
        _ = keep_compilation(seen, variation)
    return Started(runs, left_out)


def again(seen: Seen, run: RunStarted, seeds: Sequence[int]) -> Running:
    """Begins a run of the run's skeleton and cases under other seeds, at its handle's
    latest endpoint, and sends nothing.

    Stores the run's trial, start record and entries once the gate has confirmed the
    endpoint with a request to it.

    Heads-up: the gate's `Refused` passes through.
    """
    if run.endpoint is None:
        raise ValueError(
            f"run {run.run} was sent to no endpoint, so it can't run again"
        )
    ran = resolve(seen.store.get, run.trial, Trial)
    families = {f.id for f in seen.families()}
    if missing := [c for c in ran.cases if family_of(seen.rows, c) not in families]:
        raise NotFound(f"no case {missing[0]} for {seen.person.login}")
    skeleton = resolve(seen.store.get, ran.skeleton, Skeleton)
    about = read.about(seen.rows, Subject(run=run.run))
    weights = model_of(ran.engine, seen.store.get).digest
    handle = seen.handle(weights)
    if handle.weights != weights:
        raise Invalid.of(
            "run %(run)s is out of date: run its configuration instead, once that is "
            + "updated",
            run=str(run.run),
        )
    at = seen.served(handle)
    return _begun(
        seen,
        skeleton,
        at.name,
        at.engine,
        list(ran.cases),
        seeds,
        about.name or seen.title(ran.skeleton),
        _varying(about.varied, about.replaced),
        cleanup=ran.cleanup,
        execution=run.execution,
        canaries=None
        if run.canaries is None
        else resolve(seen.store.get, run.canaries, CanarySet),
        verify_at=run.verify_at,
    )


def _varying(edit: int | None, replaced: Mapping[str, str | None]) -> list[Entry]:
    if edit is None:
        return []
    return [Entry.varied(edit), *(Entry.replaced(p, d) for p, d in replaced.items())]


def resume(seen: Seen, run: RunStarted) -> Running:
    return Runner(seen.conn, seen.inventory, seen.person).resume(run.run)


def queue(seen: Seen, running: Running, score: bool = True) -> Job:
    started = running.started
    assert started.endpoint is not None
    return Queue(seen.conn).put(
        seen.person.id,
        started.run,
        started.endpoint.name,
        started.execution.concurrency,
        score,
    )


def queue_scoring(
    seen: Seen, run: RunStarted, scorers: Collection[str] | None = None
) -> list[str]:
    if run.run not in seen.store.finished([run.run]):
        raise ValueError(f"run {run.run} hasn't finished")
    applying = [e.digest for e, _, _ in seen.scorers(run)]
    if missing := [s for s in scorers or () if s not in applying]:
        raise ValueError(f"scorer {missing[0]} doesn't apply to run {run.run}")
    chosen = [s for s in applying if scorers is None or s in scorers]
    if not chosen:
        raise ValueError(f"no scorer applies to run {run.run}")
    endpoint = "" if run.endpoint is None else run.endpoint.name
    _ = Queue(seen.conn).put(seen.person.id, run.run, endpoint, 0, True, chosen)
    return chosen


def _begun(
    seen: Seen,
    skeleton: Skeleton,
    endpoint: str,
    engine: str,
    cases: list[str],
    seeds: Sequence[int],
    name: str,
    said: Sequence[Entry],
    *,
    cleanup: tuple[CleanupOp, ...],
    execution: Execution | None,
    canaries: CanarySet | None,
    verify_at: tuple[Phase, ...] = PHASES,
) -> Running:
    registry, made = trial(seen, skeleton, engine, cases, seeds, cleanup)
    return _ran(
        seen, made, registry, endpoint, name, said, execution, canaries, verify_at
    )


def _ran(
    seen: Seen,
    made: Trial,
    registry: Registry,
    endpoint: str,
    name: str,
    said: Sequence[Entry],
    execution: Execution | None,
    canaries: CanarySet | None,
    verify_at: tuple[Phase, ...] = PHASES,
) -> Running:
    check_quota(seen, [len(made.cases) * len(made.seeds)])
    runner = Runner(seen.conn, seen.inventory, seen.person)
    running = runner.start(made, registry, endpoint, execution, canaries, verify_at)
    with seen.conn.transaction():
        for entry in (Entry(field=EntryField.NAME, value=name), *said):
            seen.catalog.note(Subject(run=running.run), entry, seen.person.id)
    return running


def start_trials(
    seen: Seen,
    versions: Sequence[int],
    concurrency: int | None = None,
    order: Order | None = None,
) -> list[Running]:
    """Begins a run of each trial version at the endpoint serving its engine, and sends
    nothing.

    Stores each run's start record and entries in one transaction, which holds while the
    gate confirms the endpoint with a request to it for each run.

    Heads-up: the gate's `Refused` passes through.
    """
    found: list[tuple[Trial, str]] = []
    for id in dict.fromkeys(versions):
        held = seen.rows.edit(id)
        if held is None:
            raise NotFound(f"no trial version {id} for {seen.person.login}")
        _, about = seen.thread(held.thread, "trial")
        name = about.name or titles.title(seen.rows, held.thread)
        found.append((resolve(seen.store.get, held.digest, Trial), name))
    if not found:
        raise ValueError("a start runs one trial or more")
    seen_cases = {c for f in seen.families() for c in f.cases}
    for made, _ in found:
        if missing := [c for c in made.cases if c not in seen_cases]:
            raise NotFound(f"no case {missing[0]} for {seen.person.login}")
    check_quota(seen, [len(t.cases) * len(t.seeds) for t, _ in found])
    runs: list[Running] = []
    # Policy: one transaction, so that a run the gate refuses leaves none of the start's
    # begun.
    with seen.conn.transaction():
        for made, name in found:
            try:
                serving = seen.inventory.serving(made.engine)
            except LookupError:
                raise Invalid.of(
                    "%(name)s is out of date: update it on its page", name=name
                ) from None
            at = seen.endpoint(serving)
            canaries = at.spec.canaries
            with_first = [Entry.started_with(runs[0].run)] if runs else []
            runs.append(
                _ran(
                    seen,
                    made,
                    seen.store.load([made.digest]),
                    at.name,
                    name,
                    with_first,
                    # Policy: a concurrency asked past what the endpoint takes is what it
                    # takes, so that no start is refused for it.
                    at.spec.execution.overlaid(
                        None
                        if concurrency is None
                        else min(concurrency, at.spec.capacity),
                        order,
                    ),
                    None
                    if canaries is None
                    else resolve(seen.store.get, canaries, CanarySet),
                )
            )
    return runs


def check_quota(seen: Seen, runs: Sequence[int]) -> None:
    """Refuses with `OverQuota` runs of these many items each that the person's quota
    doesn't hold; reads how many runs they started in the last day."""
    for items in runs:
        if items > settings.ITEMS_PER_RUN:
            raise OverQuota.of(
                (
                    "a run holds at most %(num)s item, not %(given)s",
                    "a run holds at most %(num)s items, not %(given)s",
                ),
                num=settings.ITEMS_PER_RUN,
                given=items,
            )
    since = datetime.now(UTC) - timedelta(days=1)
    started = seen.rows.runs_started(seen.person.id, since)
    if started + len(runs) > settings.RUNS_PER_DAY:
        raise OverQuota.of(
            "over the day's quota: %(used)s of %(limit)s",
            used=started + len(runs),
            limit=settings.RUNS_PER_DAY,
        )


@dataclass(frozen=True)
class ScorerStarted:
    scorer: str
    name: str
    score: UUID


type ScoringEvent = ScoreEvent | ScorerStarted


def score(
    seen: Seen,
    run: RunStarted,
    scorers: Collection[str] | None = None,
    on_event: Callable[[ScoringEvent], None] | None = None,
    halt: Halt | None = None,
) -> list[Graded]:
    """Scores the run under each scorer that applies, or each of those given, one after
    another in the calling thread.

    Sends each judged view's requests to its judge's endpoint once the gate has confirmed
    it with a request to it, and writes each score's records as it goes.

    Heads-up: a scorer refused is returned with why in `Graded.refused`, not raised, and
    so is each one after a halt or an interrupt, as stopped.
    """
    found: list[Graded] = []
    stopped = False
    for edit, about, scorer in seen.scorers(run):
        if scorers is not None and edit.digest not in scorers:
            continue
        name = about.name or titles.title(seen.rows, edit.thread)
        labels = labels_of(seen, edit)
        if stopped or (halt is not None and halt.is_set()):
            stopped = True
            found.append(Graded(name, scorer, labels, refused=STOPPED))
            continue
        try:
            grading = _started(seen, run, edit.digest)
        except REFUSALS as e:
            found.append(Graded(name, scorer, labels, refused=str(e)))
            continue
        except KeyboardInterrupt:
            stopped = True
            found.append(Graded(name, scorer, labels, refused=STOPPED))
            continue
        # Policy: a scorer reading no expectation of the run's cases has nothing to
        # score, as unscored holds, rather than refusing.
        if grading is None:
            continue
        if on_event is not None:
            on_event(ScorerStarted(edit.digest, name, grading.score))
        failed: str | None = None
        try:
            grading.send(on_event, halt)
        except KeyboardInterrupt:
            stopped = True
        except REFUSALS as e:
            failed = str(e)
        given, findings = grading.finish()
        if failed is None:
            found.append(Graded(name, scorer, labels, given, findings))
        else:
            found.append(Graded(name, scorer, labels, refused=failed))
    return sorted(found, key=lambda g: g.name)


def _started(seen: Seen, run: RunStarted, scorer: str) -> Grading | None:
    built = scoring(seen, run, scorer)
    if built is None:
        return None
    pinned = [e.engine for e in built.engines]
    registry = seen.store.load([built.scorer, *built.expectations, *pinned])
    runner = Runner(seen.conn, seen.inventory, seen.person)
    return runner.score(run.run, built, registry)
