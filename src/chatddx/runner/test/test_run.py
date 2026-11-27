import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

import pytest
from pydantic import ValidationError

from chatddx.catalog import Subject, read
from chatddx.curation import Plan
from chatddx.factors.base import Code, Fingerprint, resolve
from chatddx.factors.cases import Case, Vignette, prepare_case
from chatddx.factors.engine import LocalEngine
from chatddx.factors.request import (
    Compilation,
    Skeleton,
    Tool,
    Toolset,
    compile_request,
    next_request,
)
from chatddx.factors.response import tool_calls
from chatddx.factors.trial import Canary, CanarySet, Execution, Trial, replicates
from chatddx.fake_vllm.script import Script, Turn
from chatddx.identity import Person
from chatddx.inventory import DirectorySource, Inventory
from chatddx.ledger import (
    Endpoint,
    ItemKey,
    RunFinished,
    ToolCode,
    check_run,
    fingerprint_request,
)
from chatddx.ledger.call import check_execution
from chatddx.rig import rig
from chatddx.runner.events import (
    CanaryEnded,
    ItemEnded,
    ItemStarted,
    Noted,
    RunEvent,
    Streamed,
    ToolRan,
)
from chatddx.runner.gate import Refused
from chatddx.runner.run import Runner
from chatddx.runner.send import STOPPED, Delta, Halt, send
from chatddx.runner.test.helpers import CASES, rows, trial
from chatddx.runner.test.tools import component
from chatddx.store import Rows, Store
from chatddx.store.store import Connection
from chatddx.test.helpers import connect
from chatddx.test.world import (
    GPT_OSS,
    LINES,
    NATIVE_TOOLS,
    QWEN,
    TOOL_ANSWER,
    faked,
    free_world,
)
from chatddx.tools.shipped import TOOLS, ShippedTool


@dataclass
class Heard:
    events: list[RunEvent] = field(default_factory=list[RunEvent])
    then: Callable[[RunEvent], None] | None = None

    def __call__(self, event: RunEvent) -> None:
        self.events.append(event)
        if self.then is not None:
            self.then(event)

    def of[E](self, kind: type[E]) -> list[E]:
        return [e for e in self.events if isinstance(e, kind)]


def elsewhere(f: Callable[[], None]) -> None:
    thread = threading.Thread(target=f)
    thread.start()
    thread.join()


def reasoning(ended: ItemEnded) -> str:
    response = cast(Any, ended.item.call.response)
    return response["choices"][0]["message"]["reasoning"]


@pytest.mark.usefixtures("fake")
def test_a_run_sends_each_item_and_writes_its_log(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    made = trial(plan)
    running = Runner(conn, inventory, alice).start(made, plan.registry, QWEN)
    heard = Heard()
    running.send(heard)
    assert running.finish() == []

    stored = Store(conn).run(running.run)
    started = stored.started
    assert (started.trial, started.rig, started.execution) == (
        made.digest,
        rig(),
        Execution(),
    )
    assert started.endpoint == Endpoint(
        name=QWEN, url=str(inventory.endpoint(QWEN).url)
    )
    assert isinstance(stored.finished, RunFinished) and stored.finished.findings == ()
    assert [i.key for i in heard.of(ItemStarted)] == [
        ItemKey(case=c, replicate=r) for c in made.cases for r in (0, 1)
    ]
    assert {i.key for i in stored.items} == {e.key for e in heard.of(ItemStarted)}
    assert all(i.call.error is None and i.call.status == 200 for i in stored.items)
    assert [
        f"seed={e.seed} " in reasoning(d)
        for e, d in zip(heard.of(ItemStarted), heard.of(ItemEnded), strict=True)
    ] == [True] * 4
    started = [e.key for e in heard.of(ItemStarted)]
    streamed = [s.key for s in heard.of(Streamed)]
    assert streamed == sorted(streamed, key=started.index)
    assert set(streamed) == set(started) and not heard.of(Noted)
    about = read.about(Rows(conn), Subject(run=running.run))
    assert about.owner == alice.id


@pytest.mark.usefixtures("fake")
def test_a_greedy_skeleton_is_sent_without_its_seed(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    named = plan.named("recipe", LINES)
    assert named.compilation is not None
    compiled = resolve(plan.registry.get, named.compilation, Compilation)
    greedy = compiled.recipe.model_copy(
        update={"sampling": plan.named("sampling", "greedy").digest}
    )
    skeleton = compile_request(greedy, plan.registry.get)
    assert skeleton.greedy
    made = trial(plan, cases=CASES[:1]).model_copy(
        update={"skeleton": plan.registry.add(skeleton), "seeds": (0,)}
    )
    _ = plan.registry.add(made)
    running = Runner(conn, inventory, alice).start(made, plan.registry, QWEN)
    heard = Heard()
    running.send(heard)
    _ = running.finish()
    [ended] = heard.of(ItemEnded)
    assert "seed=" not in reasoning(ended) and "temperature=0" in reasoning(ended)


@pytest.mark.usefixtures("fake")
def test_each_row_lands_as_it_is_written(
    conn: Connection, db: str, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    running = Runner(conn, inventory, alice).start(trial(plan), plan.registry, QWEN)
    assert rows(db, "run_stage") == 1
    landed: list[int] = []
    running.send(
        Heard(
            then=lambda e: (
                landed.append(rows(db, "run_item"))
                if isinstance(e, ItemEnded)
                else None
            )
        )
    )
    assert landed == [1, 2, 3, 4]
    _ = running.finish()
    assert rows(db, "run_stage") == 2


def test_the_runner_wants_rows_committed_as_they_are_written(
    db: str, inventory: Inventory, alice: Person
) -> None:
    with connect(db) as c, pytest.raises(ValueError, match="autocommit"):
        _ = Runner(c, inventory, alice)


@pytest.mark.usefixtures("fake")
def test_a_case_that_can_t_be_read_or_has_changed_is_noted(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    one = trial(plan, cases=CASES[:1], seeds=(7,))
    real = resolve(plan.registry.get, one.cases[0], Case)
    missing = Case(
        vignette=Vignette(
            source="test", id="nowhere", fingerprint=real.vignette.fingerprint
        )
    )
    changed = Case(
        vignette=real.vignette.model_copy(
            update={"fingerprint": Fingerprint.of(b"before")}
        )
    )
    made = one.model_copy(
        update={"cases": tuple(plan.registry.add(c) for c in (real, missing, changed))}
    )
    _ = plan.registry.add(made)
    running = Runner(conn, inventory, alice).start(made, plan.registry, QWEN)
    heard = Heard()
    running.send(heard)
    findings = running.finish()
    noted = sorted(n.finding.code for n in heard.of(Noted))
    assert noted == ["case.drift", "case.unreadable"]
    started = [e.key for e in heard.of(ItemStarted)]
    assert len(started) == 2
    assert started == [e.item.key for e in heard.of(ItemEnded)]
    stored = Store(conn).run(running.run)
    assert stored.finished is not None
    assert sorted(f.code for f in stored.finished.findings) == noted
    assert len(stored.items) == 2
    codes = [f.code for f in findings]
    assert "run.incomplete" in codes and "case.drift" in codes


@pytest.mark.usefixtures("fake")
def test_stopping_ends_the_run_after_the_item_under_way(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    running = Runner(conn, inventory, alice).start(trial(plan), plan.registry, QWEN)

    def stop(event: RunEvent) -> None:
        if isinstance(event, Streamed):
            running.stop()

    running.send(Heard(then=stop))
    findings = running.finish()
    assert len(Store(conn).run(running.run).items) == 1
    assert ("run.incomplete", "3 items missing") in [
        (f.code, f.message) for f in findings
    ]


@pytest.mark.usefixtures("fake")
def test_an_interrupt_mid_call_records_the_call_as_stopped(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    running = Runner(conn, inventory, alice).start(trial(plan), plan.registry, QWEN)
    deltas: list[Streamed] = []

    def interrupt(event: RunEvent) -> None:
        if isinstance(event, Streamed):
            deltas.append(event)
            if len(deltas) == 2:
                raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        running.send(Heard(then=interrupt))
    running.send()
    findings = running.finish()
    [item] = Store(conn).run(running.run).items
    assert item.call.error == STOPPED and item.call.prompt_tokens is not None
    assert ("call.failed", STOPPED, str(item.key)) in [
        (f.code, f.message, f.subject) for f in findings
    ]


def test_nothing_is_sent_or_written_where_the_gate_refuses(
    conn: Connection,
    db: str,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
) -> None:
    def refused(made: Trial, endpoint: str, at: Inventory = inventory) -> str:
        with pytest.raises(Refused) as caught:
            _ = Runner(conn, at, alice).start(made, plan.registry, endpoint)
        return str(caught.value)

    uncleared = inventory.model_copy(update={"cleared": {}})
    assert "isn't cleared for source test, which is sensitive" in refused(
        trial(plan), QWEN, uncleared
    )
    assert "serves engine" in refused(trial(plan), GPT_OSS)
    assert f"endpoint {GPT_OSS!r} can't be confirmed" in refused(
        trial(plan, engine=GPT_OSS), GPT_OSS
    )
    assert "tools can't be cleared yet" in refused(trial(plan, NATIVE_TOOLS), QWEN)
    assert rows(db, "run_stage") == 0


@pytest.mark.usefixtures("fake")
def test_a_secret_is_sent_and_never_written(
    conn: Connection,
    db: str,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyed = inventory.model_copy(
        update={
            "endpoints": inventory.endpoints
            | {
                QWEN: inventory.endpoint(QWEN).model_copy(
                    update={"credential": "FAKE_KEY"}
                )
            }
        }
    )
    monkeypatch.delenv("FAKE_KEY", raising=False)
    with pytest.raises(Refused, match=r"needs the secret in \$FAKE_KEY"):
        _ = Runner(conn, keyed, alice).start(trial(plan), plan.registry, QWEN)
    monkeypatch.setenv("FAKE_KEY", "s3cret-value")
    running = Runner(conn, keyed, alice).start(trial(plan), plan.registry, QWEN)
    running.send()
    _ = running.finish()
    with connect(db) as c:
        stored = c.execute(
            "SELECT payload FROM ledger.run_stage UNION ALL SELECT payload FROM ledger.run_item"
        ).fetchall()
    assert stored and not any("s3cret" in str(p) for (p,) in stored)


@pytest.mark.usefixtures("fake")
def test_a_run_is_finished_once_and_sends_nothing_after(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    running = Runner(conn, inventory, alice).start(trial(plan), plan.registry, QWEN)
    _ = running.finish()
    heard = Heard()
    running.send(heard)
    assert heard.events == []
    with pytest.raises(ValueError, match="is finished"):
        _ = running.finish()


ORDERS = [
    Execution(),
    Execution(order="replicate_major@1"),
    Execution(order="shuffled@1", shuffle_seed=3),
]


@pytest.mark.usefixtures("fake")
@pytest.mark.parametrize("concurrency", [1, 3])
@pytest.mark.parametrize("order", ORDERS, ids=lambda e: e.order)
def test_items_are_sent_in_the_execution_s_order(
    conn: Connection,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
    order: Execution,
    concurrency: int,
) -> None:
    made = trial(plan)
    schedules = {tuple(e.schedule(made.cases, 2)) for e in ORDERS}
    assert len(schedules) == len(ORDERS)
    execution = order.model_copy(update={"concurrency": concurrency})
    running = Runner(conn, inventory, alice).start(made, plan.registry, QWEN, execution)
    heard = Heard()
    running.send(heard)
    assert running.finish() == []
    assert [e.key for e in heard.of(ItemStarted)] == [
        ItemKey(case=c, replicate=r) for c, r in execution.schedule(made.cases, 2)
    ]
    assert Store(conn).run(running.run).started.execution == execution


@pytest.mark.usefixtures("delayed")
@pytest.mark.slow
def test_calls_are_in_flight_together_up_to_the_execution_s_concurrency(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    made = trial(plan)
    running = Runner(conn, inventory, alice).start(
        made, plan.registry, QWEN, Execution(concurrency=2)
    )
    heard = Heard()
    running.send(heard)
    assert running.finish() == []
    items = Store(conn).run(running.run).items
    assert all(i.call.error is None and i.call.status == 200 for i in items)
    calls = [i.call for i in items]
    sent = {i.key: i.call.started_at for i in items}
    assert [
        (f.code, f.message) for f in check_execution(Execution(), made, calls, sent)
    ] == [("execution.concurrency", "2 calls were in flight at once, declared 1")]
    assert {e.item.key for e in heard.of(ItemEnded)} == {
        s.key for s in heard.of(Streamed)
    }


@pytest.mark.usefixtures("fake")
def test_a_concurrency_above_the_endpoint_s_capacity_is_refused(
    conn: Connection, db: str, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    assert inventory.endpoint(QWEN).capacity == 4
    with pytest.raises(ValueError, match="takes 4 at once, the execution sends 5"):
        _ = Runner(conn, inventory, alice).start(
            trial(plan), plan.registry, QWEN, Execution(concurrency=5)
        )
    assert rows(db, "run_stage") == 0


@pytest.mark.usefixtures("delayed")
@pytest.mark.slow
def test_stopping_a_concurrent_run_ends_it_after_the_calls_in_flight(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    running = Runner(conn, inventory, alice).start(
        trial(plan), plan.registry, QWEN, Execution(concurrency=2)
    )

    def stop(event: RunEvent) -> None:
        if isinstance(event, Streamed):
            running.stop()

    running.send(Heard(then=stop))
    findings = running.finish()
    items = Store(conn).run(running.run).items
    assert [i.call.error for i in items] == [None, None]
    assert ("run.incomplete", "2 items missing") in [
        (f.code, f.message) for f in findings
    ]


@pytest.mark.usefixtures("delayed")
def test_an_interrupt_hangs_up_every_call_in_flight_and_records_them_as_stopped(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    running = Runner(conn, inventory, alice).start(
        trial(plan), plan.registry, QWEN, Execution(concurrency=2)
    )
    deltas: list[Streamed] = []

    def interrupt(event: RunEvent) -> None:
        if isinstance(event, Streamed):
            deltas.append(event)
            if len(deltas) == 2:
                raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        running.send(Heard(then=interrupt))
    running.send()
    _ = running.finish()
    items = Store(conn).run(running.run).items
    assert [i.call.error for i in items] == [STOPPED, STOPPED]
    assert all(i.call.prompt_tokens is not None for i in items)


def test_an_interrupt_ends_stalled_calls_at_once(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    with faked(inventory, plan.registry.get, delay=5.0):
        running = Runner(conn, inventory, alice).start(
            trial(plan), plan.registry, QWEN, Execution(concurrency=2)
        )
        main = threading.main_thread().ident
        assert main is not None
        threading.Timer(0.05, signal.pthread_kill, (main, signal.SIGINT)).start()
        began = time.monotonic()
        with pytest.raises(KeyboardInterrupt):
            running.send()
        assert time.monotonic() - began < 2
    _ = running.finish()
    items = Store(conn).run(running.run).items
    assert [i.call.error for i in items] == [STOPPED, STOPPED]


@pytest.mark.usefixtures("delayed")
def test_another_interrupt_while_calls_hang_up_leaves_them_out(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    running = Runner(conn, inventory, alice).start(
        trial(plan), plan.registry, QWEN, Execution(concurrency=2)
    )

    def interrupt(event: RunEvent) -> None:
        if isinstance(event, Streamed | ItemEnded):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        running.send(Heard(then=interrupt))
    _ = running.finish()
    [item] = Store(conn).run(running.run).items
    assert item.call.error == STOPPED


@pytest.mark.parametrize("concurrency", [1, 2])
def test_a_halt_from_another_thread_hangs_up_the_calls_in_flight_and_returns(
    conn: Connection,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
    concurrency: int,
) -> None:
    canaries = [Turn(content="Fine.")] * len(CANARIES.canaries)
    held = [Turn(content="Chest pain has many causes.", hold=1)] * concurrency
    deltas: list[Streamed] = []
    halt = Halt()

    def halting(event: RunEvent) -> None:
        if isinstance(event, Streamed):
            deltas.append(event)
            if len({d.key for d in deltas}) == concurrency and not halt.is_set():
                elsewhere(halt.set)

    with faked(inventory, plan.registry.get, script=Script([*canaries, *held])):
        running = Runner(conn, inventory, alice).start(
            trial(plan),
            plan.registry,
            QWEN,
            Execution(concurrency=concurrency),
            canaries=CANARIES,
        )
        running.send(Heard(then=halting), halt)
    findings = running.finish()
    stored = Store(conn).run(running.run)
    assert [i.call.error for i in stored.items] == [STOPPED] * concurrency
    assert all(i.call.prompt_tokens is not None for i in stored.items)
    assert [c.phase for c in stored.canaries] == ["start", "start"]
    assert ("run.incomplete", f"{4 - concurrency} items missing") in [
        (f.code, f.message) for f in findings
    ]


@pytest.mark.parametrize("concurrency", [1, 2])
def test_a_cut_hangs_up_the_calls_in_flight_and_records_none_for_a_resume_to_send(
    conn: Connection,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
    concurrency: int,
) -> None:
    canaries = [Turn(content="Fine.")] * len(CANARIES.canaries)
    held = [Turn(content="Chest pain has many causes.", hold=1)] * concurrency
    deltas: list[Streamed] = []
    runner = Runner(conn, inventory, alice)

    def cutting(event: RunEvent) -> None:
        if isinstance(event, Streamed):
            deltas.append(event)
            if len({d.key for d in deltas}) == concurrency:
                elsewhere(running.cut)

    with faked(inventory, plan.registry.get, script=Script([*canaries, *held])):
        running = runner.start(
            trial(plan),
            plan.registry,
            QWEN,
            Execution(concurrency=concurrency),
            canaries=CANARIES,
        )
        running.send(Heard(then=cutting))
    assert Store(conn).run(running.run).items == ()

    with faked(inventory, plan.registry.get):
        resumed = runner.resume(running.run)
        resumed.send()
    _ = resumed.finish()
    stored = Store(conn).run(running.run)
    assert len(stored.items) == 4
    assert all(i.call.error is None for i in stored.items)


@pytest.mark.usefixtures("delayed")
def test_a_call_that_fails_on_its_thread_fails_the_send_and_keeps_the_calls_beside_it(
    conn: Connection,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    streaming = threading.Event()
    calls: list[int] = []

    def broken(*args: Any, **kwargs: Any) -> Any:
        calls.append(len(calls))
        if len(calls) == 1:
            on_delta = kwargs["on_delta"]

            def heard(delta: Delta) -> None:
                streaming.set()
                on_delta(delta)

            kwargs["on_delta"] = heard
            return send(*args, **kwargs)
        assert streaming.wait(5)
        raise RuntimeError("broken")

    monkeypatch.setattr("chatddx.runner.rounds.send", broken)
    running = Runner(conn, inventory, alice).start(
        trial(plan), plan.registry, QWEN, Execution(concurrency=2)
    )
    halt = Halt()
    with pytest.raises(RuntimeError, match="broken"):
        running.send(halt=halt)
    _ = running.finish()
    [item] = Store(conn).run(running.run).items
    assert item.call.error == STOPPED and not halt.is_set()


def insensitive(inventory: Inventory) -> Inventory:
    test = inventory.sources["test"].model_copy(update={"sensitive": False})
    return inventory.model_copy(update={"sources": {"test": test}})


def tooled(
    plan: Plan,
    recipe: str,
    *tools: Tool,
    max_rounds: int = 5,
    cases: tuple[str, ...] = CASES[:1],
    seeds: tuple[int, ...] = (7,),
) -> Trial:
    named = plan.named("recipe", recipe)
    assert named.compilation is not None
    compiled = resolve(plan.registry.get, named.compilation, Compilation).recipe
    toolset = Toolset(
        tools=tuple(plan.registry.add(t) for t in tools), max_rounds=max_rounds
    )
    skeleton = compile_request(
        compiled.model_copy(update={"toolset": plan.registry.add(toolset)}),
        plan.registry.get,
        plan.facts.about(compiled.model, plan.registry.get),
    )
    made = trial(plan, cases=cases, seeds=seeds).model_copy(
        update={
            "skeleton": plan.registry.add(skeleton),
            "seeds": replicates(skeleton, seeds),
        }
    )
    _ = plan.registry.add(made)
    return made


ASKED = "'fake query'"


@pytest.mark.usefixtures("fake")
def test_a_round_runs_the_tools_a_response_calls_and_sends_back_their_results(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    open_world = insensitive(inventory)
    made = tooled(plan, LINES, component("lookup"), component("broken"))
    running = Runner(conn, open_world, alice).start(made, plan.registry, QWEN)
    heard = Heard()
    running.send(heard)
    assert running.finish() == []

    stored = Store(conn).run(running.run)
    skeleton = resolve(plan.registry.get, made.skeleton, Skeleton)
    assert stored.started.tool_code == tuple(
        ToolCode(tool=t, version=1) for t in sorted(skeleton.tools)
    )
    [item] = stored.items
    assert [[(r.name, r.result, r.error) for r in t.tools] for t in item.turns] == [
        [("lookup", f"1 results for {ASKED}", None)],
        [
            (
                "broken",
                f"error: OSError: no answer for {ASKED}",
                f"OSError: no answer for {ASKED}",
            )
        ],
    ]
    last = item.calls[-1]
    assert last.response is not None and tool_calls(last.response) == ()
    assert all(c.status == 200 and c.prompt_tokens is not None for c in item.calls)
    assert [(e.key, e.run.name) for e in heard.of(ToolRan)] == [
        (item.key, "lookup"),
        (item.key, "broken"),
    ]

    case = resolve(plan.registry.get, made.cases[0], Case)
    raw = open_world.source("test", DirectorySource).fetch(case.vignette.id)
    fills = prepare_case(
        case, raw, plan.registry.get, skeleton.appendix_layout, made.cleanup
    ).fills
    engine = resolve(plan.registry.get, made.engine, LocalEngine)
    body = skeleton.render(model=engine.digest, seed=7, fills=fills)
    assert item.call.request == fingerprint_request(body)
    assert item.call.response is not None
    results = {r.id: r.result for r in item.turns[0].tools}
    second = next_request(body, item.call.response, results)
    assert item.calls[1].request == fingerprint_request(second)


@pytest.mark.usefixtures("fake")
def test_calling_the_answer_tool_ends_the_item(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    made = tooled(plan, TOOL_ANSWER, component("lookup"))
    running = Runner(conn, insensitive(inventory), alice).start(
        made, plan.registry, QWEN
    )
    running.send()
    assert running.finish() == []
    [item] = Store(conn).run(running.run).items
    assert [[r.name for r in t.tools] for t in item.turns] == [["lookup"]]
    last = item.calls[-1].response
    assert last is not None and [c.name for c in tool_calls(last)] == ["final_result"]


@pytest.mark.usefixtures("fake")
def test_rounds_end_after_max_rounds_and_the_calls_left_are_noted(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    made = tooled(plan, LINES, component("lookup"), component("broken"), max_rounds=1)
    running = Runner(conn, insensitive(inventory), alice).start(
        made, plan.registry, QWEN
    )
    running.send()
    assert [(f.code, f.message) for f in running.finish()] == [
        (
            "tools.unanswered",
            "the last response still calls broken after 1 of 1 rounds",
        )
    ]
    [item] = Store(conn).run(running.run).items
    assert len(item.turns) == 1


@pytest.mark.usefixtures("fake")
def test_a_tool_at_a_version_the_running_code_doesn_t_ship_is_refused(
    conn: Connection, db: str, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    made = tooled(plan, LINES, component("lookup", 2))
    with pytest.raises(LookupError, match="at version 1 in chatddx .*, not 2"):
        _ = Runner(conn, insensitive(inventory), alice).start(made, plan.registry, QWEN)
    assert rows(db, "run_stage") == 0


def stopped(message: str) -> tuple[str, str]:
    return ("tools.stopped", message)


@pytest.mark.usefixtures("fake")
def test_an_interrupt_after_a_tool_ran_keeps_its_round_without_a_call(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    made = tooled(plan, LINES, component("lookup"), component("broken"))
    running = Runner(conn, insensitive(inventory), alice).start(
        made, plan.registry, QWEN
    )
    ran: list[ToolRan] = []

    def interrupt(event: RunEvent) -> None:
        if isinstance(event, ToolRan):
            ran.append(event)
            if len(ran) == 2:
                raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        running.send(Heard(then=interrupt))
    findings = running.finish()
    [item] = Store(conn).run(running.run).items
    assert [[r.name for r in t.tools] for t in item.turns] == [["lookup"], ["broken"]]
    assert item.turns[-1].call is None
    assert len(item.calls) == 2
    assert stopped("round 2 stopped after 1 of 1 tool calls, before its call") in [
        (f.code, f.message) for f in findings
    ]


@pytest.mark.usefixtures("fake")
def test_an_interrupt_inside_a_tool_records_it_as_stopped(
    conn: Connection,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupted(**_: object) -> str:
        raise KeyboardInterrupt

    monkeypatch.setitem(
        TOOLS, "chatddx.runner.test.tools:lookup", ShippedTool(1, interrupted)
    )
    made = tooled(plan, LINES, component("lookup"), component("broken"))
    running = Runner(conn, insensitive(inventory), alice).start(
        made, plan.registry, QWEN
    )
    with pytest.raises(KeyboardInterrupt):
        running.send()
    findings = running.finish()
    [item] = Store(conn).run(running.run).items
    [turn] = item.turns
    assert [(r.name, r.result, r.error) for r in turn.tools] == [
        ("lookup", f"error: {STOPPED}", STOPPED)
    ]
    assert turn.call is None
    assert stopped("round 1 stopped after 1 of 1 tool calls, before its call") in [
        (f.code, f.message) for f in findings
    ]


@pytest.mark.usefixtures("fake")
def test_a_halt_while_tools_run_keeps_the_round_and_sends_no_call(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    made = tooled(plan, LINES, component("lookup"), component("broken"))
    running = Runner(conn, insensitive(inventory), alice).start(
        made, plan.registry, QWEN
    )

    halt = Halt()

    def halting(event: RunEvent) -> None:
        if isinstance(event, ToolRan):
            elsewhere(halt.set)

    running.send(Heard(then=halting), halt)
    findings = running.finish()
    [item] = Store(conn).run(running.run).items
    assert [[r.name for r in t.tools] for t in item.turns] == [["lookup"]]
    assert item.calls == (item.call,)
    assert stopped("round 1 stopped after 1 of 1 tool calls, before its call") in [
        (f.code, f.message) for f in findings
    ]


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_rounds_run_on_the_workers_above_concurrency_1(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    made = tooled(
        plan,
        LINES,
        component("lookup"),
        component("broken"),
        cases=CASES,
        seeds=(7, 8),
    )
    running = Runner(conn, insensitive(inventory), alice).start(
        made, plan.registry, QWEN, Execution(concurrency=2)
    )
    heard = Heard()
    running.send(heard)
    assert running.finish() == []
    items = Store(conn).run(running.run).items
    assert [len(i.turns) for i in items] == [2, 2, 2, 2]
    assert sorted(str(e.key) for e in heard.of(ToolRan)) == sorted(
        str(i.key) for i in items for _ in range(2)
    )


CANARIES = CanarySet(
    canaries=(
        Canary(
            messages=({"role": "user", "content": "Name three causes of chest pain."},),
            body={"temperature": 0},
        ),
        Canary(messages=({"role": "user", "content": "What is 2+2?"},), seed=7),
    )
)


@pytest.mark.usefixtures("fake")
@pytest.mark.parametrize("concurrency", [1, 2])
def test_canaries_bracket_the_items_and_are_stored_with_the_run(
    conn: Connection,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
    concurrency: int,
) -> None:
    made = trial(plan)
    running = Runner(conn, inventory, alice).start(
        made, plan.registry, QWEN, Execution(concurrency=concurrency), CANARIES
    )
    heard = Heard()
    running.send(heard)
    assert running.finish() == []

    order = [
        "canary" if isinstance(e, CanaryEnded) else "item"
        for e in heard.events
        if isinstance(e, CanaryEnded | ItemStarted | ItemEnded)
    ]
    assert order == ["canary"] * 2 + ["item"] * 8 + ["canary"] * 2
    probes = [(e.call.phase, e.call.canary) for e in heard.of(CanaryEnded)]
    assert probes == [("start", 0), ("start", 1), ("end", 0), ("end", 1)]

    stored = Store(conn).run(running.run)
    assert stored.started.canaries == CANARIES.digest
    served = plan.named("local_engine", QWEN).digest
    for probe in stored.canaries:
        body = CANARIES.canaries[probe.canary].render(model=served)
        assert probe.call.request == fingerprint_request(body)
        assert probe.call.status == 200 and probe.call.prompt_tokens is not None
    registry = Store(conn).load([made.digest, CANARIES.digest])
    assert check_run(stored, registry) == []


@pytest.mark.usefixtures("fake")
def test_canaries_go_only_at_the_phases_planned(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    running = Runner(conn, inventory, alice).start(
        trial(plan), plan.registry, QWEN, canaries=CANARIES, verify_at=("end",)
    )
    running.send()
    assert running.finish() == []
    stored = Store(conn).run(running.run).canaries
    assert sorted((c.phase, c.canary) for c in stored) == [("end", 0), ("end", 1)]


@pytest.mark.usefixtures("fake")
def test_a_stopped_run_sends_no_end_canaries(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    running = Runner(conn, inventory, alice).start(
        trial(plan), plan.registry, QWEN, canaries=CANARIES
    )

    def stop(event: RunEvent) -> None:
        if isinstance(event, Streamed):
            running.stop()

    running.send(Heard(then=stop))
    findings = [(f.code, f.message) for f in running.finish()]
    assert ("run.incomplete", "3 items missing") in findings
    assert ("run.incomplete", "2 canary calls missing") in findings
    stored = Store(conn).run(running.run).canaries
    assert sorted(c.phase for c in stored) == ["start", "start"]


@pytest.mark.usefixtures("fake")
def test_an_interrupt_during_a_canary_records_it_as_stopped(
    conn: Connection,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    def interrupted(*args: Any, **kwargs: Any) -> Any:
        heard: list[object] = []

        def on_delta(delta: object) -> None:
            heard.append(delta)
            if len(heard) == 2:
                raise KeyboardInterrupt

        return send(*args, **{**kwargs, "on_delta": on_delta})

    monkeypatch.setattr("chatddx.runner.run.send", interrupted)
    running = Runner(conn, inventory, alice).start(
        trial(plan), plan.registry, QWEN, canaries=CANARIES
    )
    with pytest.raises(KeyboardInterrupt):
        running.send()
    findings = running.finish()
    stored = Store(conn).run(running.run)
    assert [(c.phase, c.canary, c.call.error) for c in stored.canaries] == [
        ("start", 0, STOPPED)
    ]
    assert stored.items == ()
    assert [(f.message, f.subject) for f in findings if f.code == "call.failed"] == [
        (STOPPED, "start/0")
    ]


@pytest.mark.usefixtures("fake")
def test_a_halt_during_a_canary_records_it_as_stopped_and_sends_no_items(
    conn: Connection,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = Runner(conn, inventory, alice).start(
        trial(plan), plan.registry, QWEN, canaries=CANARIES
    )

    halt = Halt()

    def halted(*args: Any, **kwargs: Any) -> Any:
        heard: list[object] = []

        def on_delta(delta: object) -> None:
            heard.append(delta)
            if len(heard) == 2:
                elsewhere(halt.set)

        return send(*args, **{**kwargs, "on_delta": on_delta})

    monkeypatch.setattr("chatddx.runner.run.send", halted)
    running.send(halt=halt)
    _ = running.finish()
    stored = Store(conn).run(running.run)
    assert [(c.phase, c.canary, c.call.error) for c in stored.canaries] == [
        ("start", 0, STOPPED)
    ]
    assert stored.items == ()


@pytest.mark.usefixtures("fake")
def test_phases_without_a_canary_set_are_refused_before_anything_is_written(
    conn: Connection, db: str, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    with pytest.raises(ValidationError, match="verify_at goes with a canary set"):
        _ = Runner(conn, inventory, alice).start(
            trial(plan), plan.registry, QWEN, verify_at=("end",)
        )
    assert rows(db, "run_stage") == 0


@pytest.mark.usefixtures("fake")
@pytest.mark.parametrize("concurrency", [1, 2])
def test_resuming_sends_what_an_unfinished_log_lacks_and_finishes_it(
    conn: Connection,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
    concurrency: int,
) -> None:
    runner = Runner(conn, inventory, alice)
    running = runner.start(
        trial(plan), plan.registry, QWEN, Execution(concurrency=concurrency), CANARIES
    )

    def stop(event: RunEvent) -> None:
        if isinstance(event, ItemEnded):
            running.stop()

    running.send(Heard(then=stop))
    before = Store(conn).run(running.run)
    resumed = runner.resume(running.run)
    heard = Heard()
    resumed.send(heard)
    assert resumed.finish() == []

    stored = Store(conn).run(running.run)
    assert len(stored.items) == 4
    assert {e.key for e in heard.of(ItemStarted)}.isdisjoint(
        i.key for i in before.items
    )
    assert [e.call.phase for e in heard.of(CanaryEnded)] == ["end", "end"]
    assert stored.finished is not None
    assert [(f.level, f.code, f.message) for f in stored.finished.findings] == [
        ("info", "run.resumed", f"resumed after {len(before.items)} of 4 items")
    ]


@pytest.mark.usefixtures("fake")
def test_a_run_resumed_with_nothing_written_by_the_rig_that_started_it_notes_nothing(
    conn: Connection, inventory: Inventory, alice: Person, plan: Plan
) -> None:
    runner = Runner(conn, inventory, alice)
    running = runner.start(trial(plan), plan.registry, QWEN)
    resumed = runner.resume(running.run)
    resumed.send()
    assert resumed.finish() == []
    finished = Store(conn).run(running.run).finished
    assert finished is not None and finished.findings == ()


@pytest.mark.usefixtures("fake")
def test_a_run_resumed_by_another_rig_says_which(
    conn: Connection,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = Runner(conn, inventory, alice)
    running = runner.start(trial(plan), plan.registry, QWEN)
    other = Code(distribution="chatddx", version="9.9.9", revision="abc123")
    monkeypatch.setattr("chatddx.runner.run.rig", lambda: other)
    resumed = runner.resume(running.run)
    resumed.send()
    _ = resumed.finish()

    finished = Store(conn).run(running.run).finished
    assert finished is not None
    [finding] = finished.findings
    assert finding.level == "warning"
    assert finding.message.startswith(
        "resumed after 0 of 4 items by chatddx 9.9.9 at abc123, where chatddx "
    )
    assert finding.message.endswith(" started it")


@pytest.mark.usefixtures("fake")
def test_a_finished_run_a_moved_endpoint_or_the_gate_keep_a_run_from_resuming(
    conn: Connection,
    db: str,
    inventory: Inventory,
    alice: Person,
    plan: Plan,
) -> None:
    runner = Runner(conn, inventory, alice)
    finished = runner.start(trial(plan), plan.registry, QWEN)
    _ = finished.finish()
    with pytest.raises(ValueError, match="is finished"):
        _ = runner.resume(finished.run)

    left = runner.start(trial(plan), plan.registry, QWEN).run
    uncleared = inventory.model_copy(update={"cleared": {}})
    with pytest.raises(Refused, match="isn't cleared for source test"):
        _ = Runner(conn, uncleared, alice).resume(left)

    moved = free_world()
    now = f"is at {moved.endpoint(QWEN).url} now"
    with faked(moved, plan.registry.get), pytest.raises(ValueError, match=now):
        _ = Runner(conn, moved, alice).resume(left)
    assert rows(db, "run_item") == 0
