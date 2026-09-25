import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Self

from pydantic_ai import (
    AgentRunEvents,
    AgentRunResultEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolCallPartDelta,
    ToolReturnPart,
)
from rich.console import Console
from rich.live import Live
from rich.text import Text

from chatddx.history.models import RunStatus, ScoreModel
from chatddx.history.record import Outcome
from chatddx.repo.entities.output.pydantic import VIEWS, OutputTrailBase
from chatddx.runtime.run import FINAL_RESULT

THINKING = "#5f87af"
LABEL = "dim"
REFUSED = "red"
VALID = "green"
LATER = "yellow"

TOKENS = len("tokens")
OUTCOME = len("completed")


@dataclass(frozen=True)
class Streamed:
    answer: Any
    thought: bool


class Transcript:
    def __init__(self, console: Console):
        self.console: Console = console
        self.at_start: bool = True
        self.labelled: bool = False

    def write(self, text: str, style: str = "") -> None:
        if self.labelled:
            text = text.lstrip()

        if text:
            self.console.out(text, style=style or None, end="", highlight=False)
            self.at_start = text.endswith("\n")
            self.labelled = False

    def begin(self, label: str | None) -> None:
        if not self.at_start:
            self.console.out("")
            self.at_start = True

        self.labelled = False

        if label:
            self.console.out(f"[{label}] ", style=LABEL, end="", highlight=False)
            self.at_start = False
            self.labelled = True

    def usage(self, input_tokens: int, output_tokens: int, requests: int) -> None:
        self.begin(None)
        rounds = f", {requests} requests" if requests > 1 else ""
        self.console.out(
            f"({input_tokens} in, {output_tokens} out{rounds})",
            style=LABEL,
            highlight=False,
        )


async def show_events(console: Console, events: AgentRunEvents[Any]) -> Streamed:
    out = Transcript(console)
    answer: Any = None
    thought = False

    async for event in events:
        match event:
            case PartStartEvent(part=ThinkingPart(content=text, id=origin)):
                out.begin(_thinking(origin))
                out.write(text, THINKING)
                thought = True
            case PartDeltaEvent(delta=ThinkingPartDelta(content_delta=text)) if text:
                out.write(text, THINKING)
                thought = True
            case PartStartEvent(part=TextPart(content=text)):
                out.begin(None)
                out.write(text)
            case PartDeltaEvent(delta=TextPartDelta(content_delta=text)):
                out.write(text)
            case PartStartEvent(part=ToolCallPart(tool_name=name, args=args)):
                out.begin(name)
                out.write(_arguments(args))
            case PartDeltaEvent(delta=ToolCallPartDelta(args_delta=args)) if args:
                out.write(_arguments(args))
            case FunctionToolResultEvent(part=ToolReturnPart(content=content)):
                out.begin("result")
                out.write(_arguments(content))
                out.begin(None)
            case PartEndEvent():
                out.begin(None)
            case AgentRunResultEvent(result=result):
                answer = result.output
                usage = result.usage
                out.usage(usage.input_tokens, usage.output_tokens, usage.requests)
            case _:
                pass

    return Streamed(answer, thought)


class Columns:
    def __init__(self, cases: Iterable[str], scorers: Iterable[str]):
        self.case: int = max([len("case"), *(len(name) for name in cases)])
        self.scorers: tuple[str, ...] = tuple(scorers)

    def header(self) -> Text:
        return Text(
            "  ".join(
                (
                    f"{'case':<{self.case}}",
                    f"{'tokens':>{TOKENS}}",
                    f"{'outcome':<{OUTCOME}}",
                    *self.scorers,
                )
            ).rstrip(),
            style="bold",
        )


class Tally:
    def __init__(self, console: Console, columns: Columns, case: str):
        self.console: Console = console
        self.columns: Columns = columns
        self.case: str = case
        self.tokens: int = 0
        self.counted: bool = False
        self.last: bool = False
        self.live: Live = Live(self._line(), console=console, auto_refresh=False)

    def __enter__(self) -> Self:
        self.live.start(refresh=True)
        return self

    def __exit__(self, *_: object) -> None:
        if self.last:
            self.last = False
            self.live.update(self._line())

        self.live.stop()

        if not self.console.is_terminal:
            self.console.line()

    def count(self) -> None:
        self.tokens += 1
        self.live.update(self._line(), refresh=True)

    def stopping(self) -> None:
        self.last = True
        self.live.update(self._line(), refresh=True)

    def total(self, tokens: int) -> None:
        self.tokens = tokens
        self.counted = True
        self.live.update(self._line(), refresh=True)

    def end(self, outcome: Outcome, scores: Iterable[ScoreModel]) -> None:
        word, style = _outcome_word(outcome)
        values = {score.scorer_name: value_of(score.value) for score in scores}
        self.last = False
        line = self._line()
        line.append("  ")
        line.append(word, style=style)

        if values:
            line.append(" " * (OUTCOME - len(word)))

            for scorer in self.columns.scorers:
                line.append(f"  {values.get(scorer, ''):<{len(scorer)}}")

        if outcome.error is not None:
            line.append(f"  {clipped_line(outcome.error)}", style=REFUSED)

        line.rstrip()
        self.live.update(line, refresh=True)

    def _line(self) -> Text:
        tokens = (
            str(self.tokens) if self.counted or not self.tokens else f"~{self.tokens}"
        )
        line = Text(f"{self.case:<{self.columns.case}}  {tokens:>{TOKENS}}")

        if self.last:
            line.append("  stopping after this case (Ctrl-C again stops it now)", LATER)

        return line


async def tally_events(events: AgentRunEvents[Any], tally: Tally) -> Streamed:
    answer: Any = None
    thought = False

    async for event in events:
        match event:
            case PartStartEvent(part=part):
                thought = thought or isinstance(part, ThinkingPart)
                tally.count()
            case PartDeltaEvent(delta=delta):
                thought = thought or isinstance(delta, ThinkingPartDelta)
                tally.count()
            case AgentRunResultEvent(result=result):
                answer = result.output
                tally.total(result.usage.output_tokens)
            case _:
                pass

    return Streamed(answer, thought)


def show_messages(
    console: Console, messages: list[ModelMessage], answered: bool
) -> None:
    out = Transcript(console)
    responses = [message for message in messages if isinstance(message, ModelResponse)]

    for message in messages:
        match message:
            case ModelResponse(parts=parts):
                for part in parts:
                    match part:
                        case ThinkingPart(content=text, id=origin):
                            out.begin(_thinking(origin))
                            out.write(text, THINKING)
                        case TextPart(content=text):
                            out.begin(None)
                            out.write(text)
                        case ToolCallPart(tool_name=name, args=args):
                            out.begin(name)
                            out.write(_arguments(args))
                        case _:
                            pass

                    out.begin(None)
            case ModelRequest(parts=parts):
                for part in parts:
                    if (
                        isinstance(part, ToolReturnPart)
                        and part.tool_name != FINAL_RESULT
                    ):
                        out.begin("result")
                        out.write(_arguments(part.content))
                        out.begin(None)

    if answered:
        out.usage(
            sum(response.usage.input_tokens for response in responses),
            sum(response.usage.output_tokens for response in responses),
            len(responses),
        )


def show_validity(console: Console, problem: str | None) -> None:
    if problem is None:
        console.print("valid", style=VALID)
    else:
        console.print(Text(f"invalid: {problem}", style=REFUSED))


def show_views(console: Console, output: OutputTrailBase, answer: Any) -> None:
    for view in VIEWS:
        if view == "text" or view not in output.views:
            continue

        items = output.view(view, answer)
        console.print(view, style="bold")

        for i, item in enumerate(items, 1):
            text = item if isinstance(item, str) else json.dumps(item)
            console.print(Text(f"  {i}. {text}"))

        if not items:
            console.print("  nothing", style=LABEL)


def show_scores(console: Console, scores: Iterable[ScoreModel]) -> None:
    rows = list(scores)

    if not rows:
        return

    console.print("scores", style="bold")
    width = max(len(score.scorer_name) for score in rows)

    for score in rows:
        text = Text(f"  {score.scorer_name:<{width}}  {value_of(score.value):<5}")

        if score.answer is not None:
            text.append(f"  {clipped_line(score.answer)}")
        elif score.reason is not None:
            text.append(f"  {score.reason}", style=LABEL)

        console.print(text)


def value_of(value: float | None) -> str:
    if value is None:
        return "—"

    return str(int(value)) if value.is_integer() else f"{value:.3g}"


def clipped_line(text: str, width: int = 60) -> str:
    line = text.splitlines()[0] if text else ""
    return line if len(line) <= width else line[: width - 1] + "…"


def _outcome_word(outcome: Outcome) -> tuple[str, str]:
    if outcome.status == RunStatus.ERRORED:
        return "errored", REFUSED

    match outcome.valid:
        case True:
            return "valid", VALID
        case False:
            return "invalid", REFUSED
        case None:
            return "completed", ""


def _thinking(origin: str | None) -> str:
    return "thinking in content" if origin == "content" else "thinking"


def _arguments(args: Any) -> str:
    match args:
        case str():
            return args
        case None:
            return ""
        case dict():
            return json.dumps(args)
        case _:
            return str(args)
