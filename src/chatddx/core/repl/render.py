"""How a run is written out: as it streams, and again from its record."""

import json
from dataclasses import dataclass
from typing import Any

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
from rich.text import Text

from chatddx.repo.entities.output.pydantic import OutputTrailBase
from chatddx.runtime.trial import FINAL_RESULT

THINKING = "#5f87af"
LABEL = "dim"
REFUSED = "red"
VALID = "green"
LATER = "yellow"


@dataclass(frozen=True)
class Streamed:
    """A run's answer, and whether any of the model's thinking came back."""

    answer: Any
    thought: bool


class Transcript:
    """A run written out as it comes: each part on a line of its own, labelled."""

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
    """
    Write out a trial's events as they come: its thinking, then its answer,
    as text or as the call that gives it.
    """
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


def show_messages(
    console: Console, messages: list[ModelMessage], answered: bool
) -> None:
    """
    Write out a recorded run's messages as its events came when it ran, and
    what it used, if it came to an answer. What the answer's own tool
    returns, the model never reads.
    """
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
    """What each of the output's views reads from the answer."""
    for view in output.views:
        items = output.view(view, answer)
        console.print(view, style="bold")

        for i, item in enumerate(items, 1):
            text = item if isinstance(item, str) else json.dumps(item)
            console.print(Text(f"  {i}. {text}"))

        if not items:
            console.print("  nothing", style=LABEL)


def _thinking(origin: str | None) -> str:
    """
    Thinking, and whether pydantic-ai found it between <think> tags in the
    content, where no reasoning parser took it out.
    """
    return "thinking in content" if origin == "content" else "thinking"


def _arguments(args: Any) -> str:
    """A tool call's arguments, or a piece of them, as they were sent."""
    match args:
        case str():
            return args
        case None:
            return ""
        case dict():
            return json.dumps(args)
        case _:
            return str(args)
