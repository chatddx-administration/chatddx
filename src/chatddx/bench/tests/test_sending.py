import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from chatddx.bench.bench import Bench, Trial
from chatddx.bench.sending import ENDED, TICK, Handed, Relay, Sending, Tokens
from chatddx.conftest import Stalling
from chatddx.dev.fake_vllm import FakeTransport
from chatddx.history.models import ConversationContext, RunModel

pytestmark = pytest.mark.django_db


def sent(transport: Any) -> Sending:
    """free-text on case-1, sent through `transport` as the worker sends it."""
    bench = Bench("alice", transport)
    ready = bench.ready(bench.cell_of("free-text", "qwen3-8b-awq@fake"))
    [case] = [case for case in bench.cases() if case.name == "case-1"]

    return Sending(bench, Trial.on(ready, case, 42), ConversationContext.WORKER)


@pytest.fixture
def sending(fake: FakeTransport) -> Sending:
    return sent(fake)


def test_a_trial_sent_comes_to_its_outcome_and_is_written_down_once(
    sending: Sending,
):
    with Handed(sending.events()) as handed:
        events = list(handed)

    assert events
    assert sending.outcome is not None and sending.outcome.status == "completed"
    assert sending.tokens.counted and str(sending.tokens).isdigit()

    written = sending.written()

    assert written.run is not None and written.unrecorded is None
    assert written.run.conversation is not None
    assert written.run.conversation.context == "worker"
    assert {score.scorer_name for score in written.scores} == {
        "first_mention",
        "reciprocal_rank",
    }
    assert sending.written() is written
    assert RunModel.objects.count() == 1


def test_a_trial_stopped_on_its_way_is_written_down_stopped(stalling: Stalling):
    sending = sent(stalling)

    with Handed(sending.events()) as handed:
        for _ in handed:
            handed.stop()

    written = sending.written()

    assert sending.outcome is not None and sending.outcome.error == "stopped"
    assert written.run is not None
    assert (written.run.status, written.run.error) == ("errored", "stopped")
    assert stalling.aborted == stalling.requests


def test_a_trial_never_sent_is_written_down_only_once_stopped(sending: Sending):
    assert sending.written().run is None

    sending.stop()

    assert sending.written().run is not None


def test_the_tokens_are_tallied_as_the_repl_tallies_them():
    tokens = Tokens()

    assert str(tokens) == "0"

    tokens.count = 3

    assert str(tokens) == "~3"

    tokens.count, tokens.counted = 7, True

    assert str(tokens) == "7"


async def quiet_then(event: Any) -> AsyncGenerator[Any]:
    await asyncio.sleep(0.2)
    yield event


def test_a_handed_stream_ticks_where_nothing_came_for_a_while():
    with Handed(quiet_then("said"), tick=0.05) as handed:
        events = list(handed)

    assert events[-1] == "said"
    assert TICK in events[:-1]


def test_a_handed_stream_stopped_before_it_began_just_ends():
    handed = Handed(quiet_then("said"))
    handed.stop()

    with handed:
        assert list(handed) == []


async def said(*words: str) -> AsyncGenerator[str]:
    for word in words:
        await asyncio.sleep(0.01)
        yield word


def relayed(relay: Relay[str], streams: int) -> dict[str, list[Any]]:
    """What the relay hands over, by stream, till `streams` have ended."""
    heard: dict[str, list[Any]] = {}
    ended = 0

    while ended < streams:
        for key, event in relay.taken(timeout=5):
            heard.setdefault(key, []).append(event)
            ended += event is ENDED

    return heard


def test_a_relay_hands_its_streams_over_as_they_come_each_with_its_key():
    with Relay[str]() as relay:
        relay.start("first", said("one", "two", "three"))
        relay.start("second", said("four"))

        heard = relayed(relay, 2)

    assert heard == {
        "first": ["one", "two", "three", ENDED],
        "second": ["four", ENDED],
    }


def test_a_stream_of_a_relay_stopped_ends_where_it_is_and_the_rest_go_on():
    with Relay[str]() as relay:
        relay.start("stopped", quiet_then("never"))
        relay.start("going", said("on"))
        relay.stop("stopped")

        heard = relayed(relay, 2)

    assert heard == {"stopped": [ENDED], "going": ["on", ENDED]}


def test_a_relay_closed_stops_what_it_relays():
    relay = Relay[str]()
    relay.start("unheard", quiet_then("never"))
    relay.close()

    assert relay.taken(timeout=0) == [("unheard", ENDED)]
