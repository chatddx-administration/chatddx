import asyncio
import hashlib
import json
import tomllib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Annotated, Any, override
from unittest import mock
from urllib.parse import quote

import httpx2
import typer

from chatddx.bench.bench import Bench, Trial
from chatddx.bench.sending import Handed, Sending
from chatddx.dev.fake_vllm import Call, Reply, streamed
from chatddx.history.models import ConversationContext, RunModel

HERE = Path(__file__).parent

SAMPLES = ("typical", "broken", "rich")

# what httpx says of a stream the server went away from mid-answer
BROKEN_OFF = (
    "peer closed connection without sending complete message body "
    + "(incomplete chunked read)"
)


@dataclass(frozen=True)
class Turn:
    """What the LLM answers a request with, and whether it breaks off after."""

    reply: Reply
    # the server goes away once what the reply holds is streamed: no finish,
    # and no usage
    broken: bool = False


@dataclass(frozen=True)
class Script:
    """A sample: the cell and the case it runs, each turn, and the web it searches."""

    name: str
    configuration: str
    stack: str
    case: str
    seed: int | None
    # what the cell sets in place of the configuration's own
    set: dict[str, str]
    turns: list[Turn]
    web: dict[str, Any]

    @classmethod
    def of(cls, name: str) -> "Script":
        data = tomllib.loads((HERE / f"{name}.toml").read_text())

        return cls(
            name,
            data["configuration"],
            data["stack"],
            data["case"],
            data.get("seed"),
            data.get("set", {}),
            [_turn(name, i, turn) for i, turn in enumerate(data["turns"])],
            data.get("web", {}),
        )


def _turn(name: str, at: int, turn: dict[str, Any]) -> Turn:
    calls = tuple(
        Call(
            call["name"],
            arguments
            if isinstance(arguments := call["arguments"], str)
            else json.dumps(arguments),
            # as vLLM names a call: at random, here as the script has it
            "chatcmpl-tool-" + hashlib.md5(f"{name} {at} {n}".encode()).hexdigest(),
        )
        for n, call in enumerate(turn.get("calls", []))
    )
    finish = "tool_calls" if calls else "stop"

    return Turn(
        Reply(turn.get("reasoning"), turn.get("content", ""), calls, finish),
        turn.get("broken", False),
    )


class Scripted(httpx2.AsyncBaseTransport):
    """
    A vLLM that answers each request with the script's next turn, streamed
    as vLLM streams it, `pace` seconds between the tokens.
    """

    def __init__(self, turns: list[Turn], pace: float = 0.0):
        self.turns: list[Turn] = turns
        self.pace: float = pace
        self.answered: int = 0

    @override
    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        if self.answered == len(self.turns):
            raise RuntimeError("the script has no turn left to answer with")

        turn = self.turns[self.answered]
        self.answered += 1

        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_Streamed(json.loads(request.content), turn, self.pace),
        )


class _Streamed(httpx2.AsyncByteStream):
    def __init__(self, body: dict[str, Any], turn: Turn, pace: float):
        self._body: dict[str, Any] = body
        self._turn: Turn = turn
        self._pace: float = pace

    @override
    async def __aiter__(self) -> AsyncIterator[bytes]:
        for event in streamed(self._body, self._turn.reply):
            # what ends a reply: its finish, then its usage and [DONE]
            if self._turn.broken and '"finish_reason": "' in event:
                raise httpx2.RemoteProtocolError(BROKEN_OFF)

            if self._pace:
                await asyncio.sleep(self._pace)

            yield event.encode()


class Web:
    """
    The web as a script cans it: for each search, the results DuckDuckGo
    lists, as web_search reads them, or a status it fails with.
    """

    def __init__(self, searches: dict[str, Any]):
        self.searches: dict[str, Any] = searches

    def get(self, url: str, params: dict[str, Any] | None = None, **_: Any) -> Any:
        query = str((params or {}).get("q", ""))
        request = httpx2.Request("GET", url, params=params)
        found = self.searches.get(query, {})

        if "status" in found:
            return httpx2.Response(found["status"], request=request, text="")

        return httpx2.Response(
            200, request=request, text=_listed(found.get("results", []))
        )


def _listed(results: list[dict[str, str]]) -> str:
    """Results, as DuckDuckGo's HTML search lists them: each link through its own."""
    rows = [
        '<div class="result results_links web-result"><h2 class="result__title">'
        + f'<a rel="nofollow" class="result__a" href="{_through(result["url"])}">'
        + f"{escape(result['title'])}</a></h2>"
        + f'<a class="result__snippet" href="{_through(result["url"])}">'
        + f"{escape(result['snippet'])}</a></div>"
        for result in results
    ]

    return f'<html><body><div id="links">{"".join(rows)}</div></body></html>'


def _through(url: str) -> str:
    return escape(f"//duckduckgo.com/l/?uddg={quote(url, safe='')}&rut=0")


def sample(
    owner: str, name: str, case: str | None = None, pace: float = 0.0
) -> RunModel:
    """
    The sample `name` run for `owner`, on its script's case or on `case`, as
    the worker runs a batch's trial.
    """
    script = Script.of(name)
    bench = Bench(owner, Scripted(script.turns, pace))
    ready = bench.ready(bench.cell_of(script.configuration, script.stack, script.set))
    wanted = case or script.case
    found = next((each for each in bench.cases() if each.name == wanted), None)

    if found is None:
        raise ValueError(f"{owner} has no case '{wanted}' to run the {name} sample on")

    sending = Sending(
        bench, Trial.on(ready, found, script.seed), ConversationContext.WORKER
    )

    # web_search's own code runs; what it reaches is canned
    with (
        mock.patch("httpx2.get", Web(script.web).get),
        Handed(sending.events()) as handed,
    ):
        for _ in handed:
            pass

    written = sending.written()

    if written.run is None:
        raise RuntimeError(
            f"the {name} sample was not written down: {written.unrecorded}"
        )

    return written.run


def samples(
    owner: Annotated[str, typer.Argument()],
    only: Annotated[
        list[str] | None,
        typer.Option("--sample", help=f"one of {', '.join(SAMPLES)}; all by default"),
    ] = None,
    case: Annotated[
        str | None,
        typer.Option(help="the case to run them on; each script's own by default"),
    ] = None,
    pace: Annotated[
        float, typer.Option(help="seconds between the streamed tokens")
    ] = 0.01,
):
    """Make the sample runs for OWNER: runs to look at, answered by a script."""
    for name in only or SAMPLES:
        run = sample(owner, name, case, pace)
        description = run.conversation.description if run.conversation else ""
        typer.echo(f"{name}: run {str(run.uuid)[:8]}, {run.status}: {description}")
