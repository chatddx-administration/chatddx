import queue
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import AbstractContextManager, nullcontext
from datetime import UTC, datetime
from uuid import UUID, uuid4

from chatddx.catalog import Entry, EntryField, Subject
from chatddx.factors.base import (
    Code,
    Finding,
    Fingerprint,
    Invalid,
    StructuralError,
    resolve,
)
from chatddx.factors.bundle import Registry
from chatddx.factors.engine import served_model_name
from chatddx.factors.request import Skeleton
from chatddx.factors.scoring import Scoring
from chatddx.factors.trial import CanarySet, Execution, Trial
from chatddx.identity import Person
from chatddx.inventory import Inventory
from chatddx.ledger import (
    Call,
    CanaryCall,
    Endpoint,
    ItemKey,
    Run,
    RunItem,
    RunStarted,
    ToolRun,
    check_run,
)
from chatddx.ledger.run import PHASES, Phase
from chatddx.rig import rig
from chatddx.store import Catalog, Store
from chatddx.store.store import Connection

from .events import (
    CanaryEnded,
    ItemEnded,
    ItemStarted,
    Noted,
    RunEvent,
    Streamed,
    ToolRan,
)
from .gate import admit
from .prepare import Items, PreparedItem
from .rounds import Exchange, Toolbox, converse, load
from .score import Grading, grade
from .send import Delta, Halt, Stopped, send


def _now() -> datetime:
    return datetime.now(UTC)


def _ignore(_: RunEvent) -> None:
    pass


def _streamed(
    key: ItemKey, emit: Callable[[Streamed], None]
) -> Callable[[Delta], None]:
    return lambda delta: emit(Streamed(key, delta))


def _ran(key: ItemKey, emit: Callable[[ToolRan], None]) -> Callable[[ToolRun], None]:
    return lambda run: emit(ToolRan(key, run))


class Runner:
    def __init__(self, conn: Connection, inventory: Inventory, by: Person) -> None:
        if not conn.autocommit:
            raise ValueError("the runner needs a connection in autocommit mode")
        self._conn: Connection = conn
        self._inventory: Inventory = inventory
        self._by: Person = by

    def start(
        self,
        trial: Trial,
        registry: Registry,
        endpoint: str,
        execution: Execution | None = None,
        canaries: CanarySet | None = None,
        verify_at: tuple[Phase, ...] = PHASES,
    ) -> "Running":
        execution = execution or Execution()
        _ = registry.add(trial)
        canary_set = None if canaries is None else registry.add(canaries)
        secret, toolbox, url = self._admitted(trial, registry, endpoint, execution)
        started = RunStarted(
            run=uuid4(),
            at=_now(),
            rig=rig(),
            trial=trial.digest,
            execution=execution,
            canaries=canary_set,
            verify_at=verify_at,
            tool_code=() if toolbox is None else toolbox.code,
            endpoint=Endpoint(name=endpoint, url=url),
        )
        store = Store(self._conn)
        roots = [trial.digest] if canary_set is None else [trial.digest, canary_set]
        _ = store.add(registry, roots)
        store.append(started)
        Catalog(self._conn).note(
            Subject(run=started.run),
            Entry(field=EntryField.OWNER, person=self._by.id),
            self._by.id,
        )
        return Running(
            self._conn, self._inventory, registry, started, url, secret, toolbox
        )

    def resume(self, run: UUID) -> "Running":
        store = Store(self._conn)
        log = store.run(run)
        started = log.started
        if log.finished is not None:
            raise ValueError(f"run {run} is finished")
        if started.endpoint is None:
            raise ValueError(f"run {run} was sent to no endpoint, so it can't resume")
        canaries = [] if started.canaries is None else [started.canaries]
        registry = store.load([started.trial, *canaries])
        trial = resolve(registry.get, started.trial, Trial)
        endpoint = started.endpoint
        secret, toolbox, url = self._admitted(
            trial, registry, endpoint.name, started.execution
        )
        if url != endpoint.url:
            raise ValueError(
                f"endpoint {endpoint.name!r} is at {url} now, and run {run} was sent "
                + f"to {endpoint.url}"
            )
        return Running(
            self._conn,
            self._inventory,
            registry,
            started,
            url,
            secret,
            toolbox,
            items=log.items,
            canaries=log.canaries,
            findings=_resumed(log, trial),
        )

    def score(
        self,
        run: UUID,
        scoring: Scoring,
        registry: Registry,
        execution: Execution | None = None,
    ) -> Grading:
        return grade(
            self._conn, self._inventory, self._by, run, scoring, registry, execution
        )

    def _admitted(
        self, trial: Trial, registry: Registry, endpoint: str, execution: Execution
    ) -> tuple[str | None, Toolbox | None, str]:
        secret = admit(self._inventory, registry.get, endpoint, trial)
        toolbox = load(resolve(registry.get, trial.skeleton, Skeleton), registry.get)
        spec = self._inventory.endpoint(endpoint)
        if execution.concurrency > spec.capacity:
            raise Invalid.raw(
                "endpoint %(endpoint)s takes %(num)s at once, the execution sends "
                + "%(sends)s",
                endpoint=repr(endpoint),
                num=spec.capacity,
                sends=execution.concurrency,
            )
        return secret, toolbox, str(spec.url)


# Policy: a run the request started and the worker sends is resumed with nothing written
# yet.
def _resumed(log: Run, trial: Trial) -> list[Finding]:
    done, num = len(log.items), len(trial.cases) * len(trial.seeds)
    if (now := rig()) != log.started.rig:
        return [
            Finding.of(
                "run.resumed",
                (
                    "resumed after %(done)s of %(num)s items by %(now)s, where "
                    + "%(then)s started it",
                    "resumed after %(done)s of %(num)s items by %(now)s, where "
                    + "%(then)s started it",
                ),
                done=done,
                num=num,
                now=_built(now),
                then=_built(log.started.rig),
            )
        ]
    if log.items or log.canaries:
        return [
            Finding.of(
                "run.resumed",
                (
                    "resumed after %(done)s of %(num)s items",
                    "resumed after %(done)s of %(num)s items",
                ),
                level="info",
                done=done,
                num=num,
            )
        ]
    return []


def _built(code: Code) -> str:
    return f"{code.distribution} {code.version}" + (
        f" at {code.revision}" if code.revision else ""
    )


class Running:
    def __init__(
        self,
        conn: Connection,
        inventory: Inventory,
        registry: Registry,
        started: RunStarted,
        url: str,
        secret: str | None,
        toolbox: Toolbox | None,
        items: Sequence[RunItem] = (),
        canaries: Sequence[CanaryCall] = (),
        findings: Sequence[Finding] = (),
    ) -> None:
        self._conn: Connection = conn
        self._store: Store = Store(conn)
        self._inventory: Inventory = inventory
        self._registry: Registry = registry
        self._started: RunStarted = started
        self._url: str = url
        self._secret: str | None = secret
        self._toolbox: Toolbox | None = toolbox
        self._prepare: Items = Items(conn, inventory, registry.get, started.trial)
        self._items: list[RunItem] = list(items)
        self._canaries: list[CanaryCall] = list(canaries)
        self._findings: list[Finding] = list(findings)
        self._stopping: bool = False
        self._cutting: bool = False
        self._halt: Halt = Halt()
        self._finished: bool = False

    @property
    def run(self) -> UUID:
        return self._started.run

    @property
    def started(self) -> RunStarted:
        return self._started

    def stop(self) -> None:
        self._stopping = True

    def cut(self) -> None:
        """Hangs up the calls in flight and records none of them, so that a resume sends
        them again."""
        self._stopping = self._cutting = True
        self._halt.set()

    def send(
        self,
        on_event: Callable[[RunEvent], None] | None = None,
        halt: Halt | None = None,
    ) -> None:
        emit: Callable[[RunEvent], None] = on_event or _ignore
        # Policy: its own halt, so that a worker's failure halts this run's calls and
        # not the caller's.
        self._halt = Halt()
        if self._cutting:
            self._halt.set()
        watching: AbstractContextManager[None] = (
            nullcontext() if halt is None else halt.watching(self._halt.set)
        )
        try:
            with watching:
                self._probe("start", emit)
                items = self._prepared(emit)
                if self._started.execution.concurrency == 1:
                    self._send_serially(items, emit)
                else:
                    self._send_concurrently(items, emit)
                self._probe("end", emit)
        finally:
            if halt is not None and halt.is_set():
                self._stopping = True

    def _probe(self, phase: Phase, emit: Callable[[RunEvent], None]) -> None:
        started = self._started
        if started.canaries is None or phase not in started.verify_at:
            return
        canaries = resolve(self._registry.get, started.canaries, CanarySet).canaries
        model = served_model_name(self._prepare.trial.engine, self._registry.get)
        sent = {(c.phase, c.canary) for c in self._canaries}
        for index, canary in enumerate(canaries):
            if self._stopped():
                return
            if (phase, index) in sent:
                continue
            try:
                call = send(
                    self._url,
                    canary.render(model=model),
                    execution=started.execution,
                    secret=self._secret,
                    halt=self._halt,
                )
            except Stopped as stopped:
                self._stopping = True
                if self._cutting:
                    return
                self._probed(phase, index, stopped.call, emit)
                if self._halt.is_set():
                    return
                raise KeyboardInterrupt from None
            self._probed(phase, index, call, emit)

    def _probed(
        self, phase: Phase, index: int, call: Call, emit: Callable[[RunEvent], None]
    ) -> None:
        record = CanaryCall(run=self.run, phase=phase, canary=index, call=call)
        self._store.append(record)
        self._canaries.append(record)
        emit(CanaryEnded(record))

    def _prepared(self, emit: Callable[[RunEvent], None]) -> Iterator[PreparedItem]:
        trial = self._prepare.trial
        sent = {i.key for i in self._items}
        schedule = self._started.execution.schedule(trial.cases, len(trial.seeds))
        for case, replicate in schedule:
            key = ItemKey(case=case, replicate=replicate)
            if self._stopped():
                return
            if key in sent:
                continue
            try:
                prepared = self._prepare.item(key)
            except (LookupError, StructuralError) as e:
                self._note(
                    Finding(code="case.unreadable", message=str(e), subject=str(key)),
                    emit,
                )
                continue
            emit(ItemStarted(key, prepared.seed))
            for finding in prepared.findings:
                self._note(finding, emit)
            yield prepared

    def _send_serially(
        self, items: Iterator[PreparedItem], emit: Callable[[RunEvent], None]
    ) -> None:
        for item in items:
            exchange = converse(
                self._url,
                item.body,
                self._toolbox,
                execution=self._started.execution,
                secret=self._secret,
                on_delta=_streamed(item.key, emit),
                on_tool=_ran(item.key, emit),
                halt=self._halt,
            )
            self._append(item.key, item.vignette, exchange, emit)
            if exchange.stopped:
                self._stopping = True
                if self._halt.is_set():
                    return
                raise KeyboardInterrupt

    def _send_concurrently(
        self, items: Iterator[PreparedItem], emit: Callable[[RunEvent], None]
    ) -> None:
        execution = self._started.execution
        results: queue.SimpleQueue[Streamed | ToolRan | Future[Exchange]] = (
            queue.SimpleQueue()
        )
        halt = self._halt
        in_flight: dict[Future[Exchange], PreparedItem] = {}
        pool = ThreadPoolExecutor(execution.concurrency, "chatddx-runner")

        def work(item: PreparedItem, started_at: datetime) -> Exchange:
            return converse(
                self._url,
                item.body,
                self._toolbox,
                execution=execution,
                secret=self._secret,
                on_delta=_streamed(item.key, results.put),
                on_tool=_ran(item.key, results.put),
                halt=halt,
                started_at=started_at,
            )

        try:
            more = True
            while True:
                while more and len(in_flight) < execution.concurrency:
                    item = next(items, None)
                    if item is None:
                        more = False
                        break
                    future = pool.submit(work, item, _now())
                    in_flight[future] = item
                    future.add_done_callback(results.put)
                if not in_flight:
                    return
                done = results.get()
                if isinstance(done, Streamed | ToolRan):
                    emit(done)
                    continue
                item = in_flight.pop(done)
                self._append(item.key, item.vignette, done.result(), emit)
        except BaseException as e:
            halt.set()
            if isinstance(e, KeyboardInterrupt):
                self._stopping = True
            while in_flight:
                done = results.get()
                if isinstance(done, Streamed | ToolRan):
                    continue
                item = in_flight.pop(done, None)
                if item is not None and done.exception() is None:
                    self._append(item.key, item.vignette, done.result(), emit)
            raise
        finally:
            if in_flight:
                halt.set()
            pool.shutdown(wait=False)

    def _stopped(self) -> bool:
        return self._stopping or self._finished or self._halt.is_set()

    def finish(self) -> list[Finding]:
        if self._finished:
            raise ValueError(f"run {self.run} is finished")
        run = Run(
            started=self._started,
            items=tuple(self._items),
            canaries=tuple(self._canaries),
        )
        finished = run.finish(_now(), self._findings)
        self._store.append(finished)
        self._finished = True
        return check_run(run.model_copy(update={"finished": finished}), self._registry)

    def _note(self, finding: Finding, emit: Callable[[RunEvent], None]) -> None:
        self._findings.append(finding)
        emit(Noted(finding))

    def _append(
        self,
        key: ItemKey,
        vignette: Fingerprint,
        exchange: Exchange,
        emit: Callable[[RunEvent], None],
    ) -> None:
        if exchange.stopped and self._cutting:
            return
        item = RunItem(
            run=self.run,
            key=key,
            vignette=vignette,
            call=exchange.call,
            turns=exchange.turns,
        )
        self._store.append(item)
        self._items.append(item)
        emit(ItemEnded(item))
