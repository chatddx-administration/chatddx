# pyright: basic
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from typing import Any, Literal

import httpx2
from django.utils import translation
from django.utils.translation import gettext, gettext_lazy as _
from pydantic_ai import (
    AgentRunResultEvent,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolReturnPart,
)

from chatddx.bench.outcome import failed, holds, unheeded
from chatddx.repo.entities.coercion.pydantic import CoercionTrailBase
from chatddx.repo.entities.instruction.pydantic import InstructionTrailBase
from chatddx.repo.entities.llm.pydantic import LLMBranchOut, LLMFacts, LLMSpecs, Refusal
from chatddx.repo.entities.output.pydantic import OutputTrailBase
from chatddx.repo.entities.reasoning.pydantic import Effort, ReasoningTrailBase
from chatddx.repo.entities.sampling.pydantic import SamplingTrailBase
from chatddx.repo.entities.stack.pydantic import StackBranchOut
from chatddx.repo.entities.tool.pydantic import ToolTrailBase
from chatddx.repo.families.fields import STORE_PATH
from chatddx.runtime.resolution import CellRefused, Resolution, Slices, resolve
from chatddx.runtime.run import Run, invalid

logger = logging.getLogger(__name__)

TRANSPORT: Any = None

SPEC = (
    "Print your spec: which model you are, who made you, your size in billions "
    + "of parameters, how many tokens of context you take in, whether you reason "
    + "before you answer, and the languages you know best."
)

SPEC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "model": {"type": "string"},
        "maker": {"type": "string"},
        "parameters_b": {"type": "number"},
        "context_tokens": {"type": "integer"},
        "reasons": {"type": "boolean"},
        "languages": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "model",
        "maker",
        "parameters_b",
        "context_tokens",
        "reasons",
        "languages",
    ],
    "additionalProperties": False,
}

READY = "Answer with one word: ready."

PROBE = ToolTrailBase(
    name="probe",
    description="This tool takes two arguments and performs an operation on them",
    parameters={
        "type": "object",
        "properties": {"v1": {"type": "integer"}, "v2": {"type": "integer"}},
        "required": ["v1", "v2"],
        "additionalProperties": False,
    },
)
PROBE_RUNS = "chatddx.runtime.tools.probe:probe"
CALL = "Call probe with v1 = 1234 and v2 = 97, and say what it returned."

SCHEMA_PROMPT = (
    "Answer with a JSON object that matches this JSON Schema, and nothing else:\n"
    + "{{schema}}"
)
TOOL_DESCRIPTION = (
    "Give your answer by calling this tool, with the answer as its arguments."
)

INSTRUCTION = InstructionTrailBase(
    system="{{schema_prompt}}",
    user="{{case}}",
    variables=["case", "schema_prompt"],
)

COERCIONS: dict[str, CoercionTrailBase] = {
    "native": CoercionTrailBase(mode="native"),
    "tool": CoercionTrailBase(mode="tool", tool_description=TOOL_DESCRIPTION),
    "prompted": CoercionTrailBase(mode="prompted", schema_prompt=SCHEMA_PROMPT),
}

ANSWER_TOKENS = 4096
BRIEF_TOKENS = 1024

SERVER_TIMEOUT = 10.0

_VLLM = re.compile(r"(?:^|-)vllm-(\d[\w.+-]*)$")

type State = Literal["waiting", "running", "passed", "failed", "warned", "skipped"]

ICONS: dict[str, str] = {
    "waiting": "radio_button_unchecked",
    "running": "progress_activity",
    "passed": "check_circle",
    "failed": "cancel",
    "warned": "warning",
    "skipped": "do_not_disturb_on",
}


@dataclass(frozen=True)
class Checked:
    key: str
    group: Literal["server", "llm"]
    title: Any
    state: State = "waiting"
    said: str = ""
    asked: str | None = None
    thinking: str = ""
    answer: str = ""
    streams: bool = False
    open: bool = False

    @property
    def icon(self) -> str:
        return ICONS[self.state]


@dataclass(frozen=True)
class Streamed:
    key: str
    kind: Literal["thinking", "answer"]
    text: str


type Event = Checked | Streamed

CHECKS: tuple[Checked, ...] = (
    Checked("reached", "server", _("Reached")),
    Checked("served", "server", _("Serves the LLM")),
    Checked("snapshot", "server", _("Loads the snapshot")),
    Checked("context", "server", _("Context")),
    Checked("engine", "server", _("Engine")),
    Checked("answers", "llm", _("Answers"), streams=True, open=True),
    Checked("off", "llm", _("Reasoning off"), streams=True),
    Checked("native", "llm", _("Native: the server holds the answer"), streams=True),
    Checked("tool", "llm", _("Tool: the answer as a call"), streams=True),
    Checked("prompted", "llm", _("Prompted: shown the schema"), streams=True),
    Checked("tools", "llm", _("Calls a tool"), streams=True),
)


@dataclass(frozen=True)
class _Toolset:
    tools: tuple[ToolTrailBase, ...]
    guidance: str | None = None


class Checking:
    def __init__(
        self,
        stack: StackBranchOut,
        llm: LLMBranchOut | None,
        api_key: str | None,
        transport: Any = None,
    ):
        self.stack: StackBranchOut = stack
        self.facts: LLMFacts = llm.details.facts if llm else LLMFacts()
        self.specs: LLMSpecs = (llm.details.specs if llm else None) or LLMSpecs()
        self.api_key: str | None = api_key
        self.transport: Any = transport
        self.language: str | None = translation.get_language()
        self.checks: dict[str, Checked] = {check.key: check for check in CHECKS}
        self.unserved: str | None = None

    async def events(self) -> AsyncIterator[Event]:
        with translation.override(self.language):
            for check in self.checks.values():
                yield check

            try:
                async for event in self._server():
                    yield event

                if self.unserved is None:
                    async for event in self._llm():
                        yield event
                else:
                    for check in self._skipped("llm", self.unserved):
                        yield check
            except Exception as e:
                logger.exception("the Test of %s broke off", self.stack.name)

                for check in self._broken(f"{type(e).__name__}: {e}"):
                    yield check

    def _broken(self, why: str) -> list[Checked]:
        running = [check for check in self.checks.values() if check.state == "running"]
        untried = gettext("not tried: the Test broke off")

        return [
            *(self._set(check.key, state="failed", said=why) for check in running),
            *self._skipped("server", untried),
            *self._skipped("llm", untried),
        ]

    def _set(self, key: str, **changed: Any) -> Checked:
        self.checks[key] = replace(self.checks[key], **changed)
        return self.checks[key]

    def _skipped(self, group: str, why: str) -> list[Checked]:
        return [
            self._set(check.key, state="skipped", said=why)
            for check in list(self.checks.values())
            if check.group == group and check.state == "waiting"
        ]

    def _unreached(self, why: str) -> list[Checked]:
        self.unserved = why
        return self._skipped("server", why)

    async def _server(self) -> AsyncIterator[Event]:
        details = self.stack.details
        refused = _unsendable(self.stack)

        if refused:
            for check in self._unreached(refused):
                yield check
            return

        if details.credential and self.api_key is None:
            yield self._set(
                "reached",
                state="failed",
                said=gettext("it takes the secret %(name)s, which you don't have")
                % {"name": details.credential},
            )
            for check in self._unreached(gettext("not tried: it can't be reached")):
                yield check
            return

        base = str(details.endpoint).rstrip("/")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

        async with httpx2.AsyncClient(
            transport=self.transport, timeout=SERVER_TIMEOUT, headers=headers
        ) as client:
            yield self._set("reached", state="running")
            listed = None
            started = time.monotonic()

            try:
                response = await client.get(f"{base}/models")
            except httpx2.HTTPError as e:
                said = gettext("can't reach %(url)s: %(error)s") % {
                    "url": base,
                    "error": f"{type(e).__name__}: {e}",
                }
                untried = gettext("not tried: it can't be reached")
            else:
                took = time.monotonic() - started
                said, listed = _listed(response, took)
                untried = gettext("not tried: the server doesn't say what it serves")

            if listed is None:
                yield self._set("reached", state="failed", said=said)
                for check in self._unreached(untried):
                    yield check
                return

            yield self._set("reached", state="passed", said=said)

            name = details.served_name
            model = next((m for m in listed if m.get("id") == name), None)

            if model is None:
                names = ", ".join(str(m.get("id")) for m in listed) or gettext(
                    "nothing"
                )
                yield self._set(
                    "served",
                    state="failed",
                    said=gettext("serves %(names)s, not %(name)s")
                    % {"names": names, "name": name},
                )
                for check in self._unreached(
                    gettext("not tried: the server doesn't serve the LLM")
                ):
                    yield check
                return

            yield self._set(
                "served",
                state="passed",
                said=gettext("serves %(name)s") % {"name": name},
            )
            yield self._snapshot(model.get("root"))
            yield self._context(model.get("max_model_len"))
            yield self._set("engine", state="running")
            yield self._engine(await _version(client, base))

    def _snapshot(self, root: Any) -> Checked:
        snapshot = self.stack.trail.llm.snapshot

        if not isinstance(root, str) or not root:
            return self._set(
                "snapshot",
                state="skipped",
                said=gettext("the server doesn't say what it loaded"),
            )

        if root == snapshot:
            return self._set(
                "snapshot",
                state="passed",
                said=gettext("loads %(root)s, the LLM's snapshot") % {"root": root},
            )

        if STORE_PATH.fullmatch(root):
            return self._set(
                "snapshot",
                state="failed",
                said=gettext("loads %(root)s, not the LLM's snapshot %(snapshot)s")
                % {"root": root, "snapshot": snapshot},
            )

        return self._set(
            "snapshot",
            state="warned",
            said=gettext(
                "loads %(root)s by its name, not from a store path: whether it is "
                + "the LLM's snapshot %(snapshot)s can't be told"
            )
            % {"root": root, "snapshot": snapshot},
        )

    def _context(self, served: Any) -> Checked:
        serving = self.stack.trail.serving
        argued = serving.args.get("max-model-len") if serving else None
        takes = self.specs.context_length

        if not isinstance(served, int):
            return self._set(
                "context",
                state="skipped",
                said=gettext("the server doesn't say how much it takes in"),
            )

        said = {"served": served, "argued": argued, "takes": takes}

        if isinstance(argued, int):
            if served == argued:
                return self._set(
                    "context",
                    state="passed",
                    said=gettext(
                        "%(served)d tokens, as its serving's max-model-len says"
                    )
                    % said,
                )

            return self._set(
                "context",
                state="failed",
                said=gettext(
                    "%(served)d tokens, where its serving's max-model-len says %(argued)d"
                )
                % said,
            )

        if takes is None:
            return self._set(
                "context",
                state="skipped",
                said=gettext(
                    "%(served)d tokens; the LLM's specs say nothing to hold it to"
                )
                % said,
            )

        if served == takes:
            return self._set(
                "context",
                state="passed",
                said=gettext("%(served)d tokens, the whole of what the LLM takes")
                % said,
            )

        if served < takes:
            return self._set(
                "context",
                state="failed",
                said=gettext(
                    "%(served)d tokens, less than the %(takes)d the LLM takes, and its "
                    + "serving sets no max-model-len"
                )
                % said,
            )

        return self._set(
            "context",
            state="warned",
            said=gettext(
                "%(served)d tokens, more than the %(takes)d the LLM's specs say"
            )
            % said,
        )

    def _engine(self, served: str | None) -> Checked:
        serving = self.stack.trail.serving

        if serving is None:
            return self._set(
                "engine",
                state="skipped",
                said=gettext(
                    "no serving is recorded: a cloud stack's engine is its own"
                ),
            )

        name = serving.engine.rpartition("/")[2].partition("-")[2]
        recorded = _VLLM.search(name)

        if served is None:
            return self._set(
                "engine",
                state="skipped",
                said=gettext("the server doesn't say its version"),
            )

        said = {"served": served, "name": name}

        if recorded is None:
            return self._set(
                "engine",
                state="skipped",
                said=gettext(
                    "vLLM %(served)s; its serving's engine, %(name)s, names no vLLM "
                    + "version to hold it to"
                )
                % said,
            )

        said["recorded"] = recorded.group(1)

        if served.partition("+")[0] == said["recorded"]:
            return self._set(
                "engine",
                state="passed",
                said=gettext("vLLM %(served)s, as its serving's engine says") % said,
            )

        return self._set(
            "engine",
            state="failed",
            said=gettext("vLLM %(served)s, where its serving's engine is %(name)s")
            % said,
        )

    async def _llm(self) -> AsyncIterator[Event]:
        quick = self._quickest()

        async for event in self._sent(
            "answers", self._slices("default", ANSWER_TOKENS), SPEC
        ):
            yield event

        off = self.facts.reasoning.resolve("off")

        if off is None:
            yield self._set(
                "off",
                state="skipped",
                said=gettext("the LLM's facts say nothing on 'off'"),
            )
        elif isinstance(off[1], Refusal):
            yield self._set("off", state="skipped", said=off[1].refused)
        else:
            async for event in self._sent(
                "off", self._slices("off", BRIEF_TOKENS), READY
            ):
                yield event

        for mode, coercion in COERCIONS.items():
            slices = self._slices(quick, BRIEF_TOKENS, coercion, SPEC_SCHEMA)

            async for event in self._sent(mode, slices, SPEC):
                yield event

        slices = self._slices(quick, BRIEF_TOKENS, toolset=_Toolset((PROBE,)))

        async for event in self._sent("tools", slices, CALL, {PROBE.name: PROBE_RUNS}):
            yield event

    def _quickest(self) -> Effort:
        for effort in ("off", "minimal", "low"):
            resolved = self.facts.reasoning.resolve(effort)

            if resolved is not None and not isinstance(resolved[1], Refusal):
                return effort

        return "default"

    def _slices(
        self,
        effort: Effort,
        max_tokens: int,
        coercion: CoercionTrailBase | None = None,
        schema: dict[str, Any] | None = None,
        toolset: _Toolset | None = None,
    ) -> Slices:
        return Slices(
            instruction=INSTRUCTION,
            output=OutputTrailBase(answer_schema=schema),
            coercion=coercion or COERCIONS["native"],
            reasoning=ReasoningTrailBase(effort=effort),
            sampling=SamplingTrailBase(defaults="recommended", max_tokens=max_tokens),
            toolset=toolset,
        )

    def _resolved(self, slices: Slices) -> Resolution:
        stack = self.stack

        try:
            return resolve(slices, stack.details, self.facts, stack.trail.serving)
        except CellRefused as e:
            if any(refusal.slice != "sampling" for refusal in e.refusals):
                raise

        sampling = slices.sampling.model_copy(update={"defaults": "generation_config"})

        return resolve(
            replace(slices, sampling=sampling),
            stack.details,
            self.facts,
            stack.trail.serving,
        )

    async def _sent(
        self,
        key: str,
        slices: Slices,
        asked: str,
        implementations: dict[str, str] | None = None,
    ) -> AsyncIterator[Event]:
        try:
            resolution = self._resolved(slices)
        except CellRefused as e:
            yield self._set(
                key,
                state="skipped",
                said="; ".join(refusal.reason for refusal in e.refusals),
            )
            return

        try:
            run = Run(
                resolution,
                asked,
                api_key=self.api_key,
                transport=self.transport,
                implementations=implementations,
            )
        except ValueError as e:
            yield self._set(key, state="failed", said=str(e))
            return

        yield self._set(key, state="running", asked=asked)

        thinking: list[str] = []
        answer: list[str] = []
        result: Any = None
        error: Exception | None = None
        sent = time.monotonic()
        first: float | None = None

        try:
            async with run.stream() as stream:
                async for event in stream:
                    match event:
                        case (
                            PartStartEvent(part=ThinkingPart(content=text))
                            | PartDeltaEvent(
                                delta=ThinkingPartDelta(content_delta=text)
                            )
                        ):
                            first = first or time.monotonic()
                            thinking.append(text or "")

                            if text:
                                yield Streamed(key, "thinking", text)
                        case (
                            PartStartEvent(part=TextPart(content=text))
                            | PartDeltaEvent(delta=TextPartDelta(content_delta=text))
                        ):
                            first = first or time.monotonic()
                            answer.append(text or "")

                            if text:
                                yield Streamed(key, "answer", text)
                        case PartStartEvent() | PartDeltaEvent():
                            first = first or time.monotonic()
                        case AgentRunResultEvent(result=done):
                            result = done
                        case _:
                            pass
        except Exception as e:  # noqa: BLE001
            error = e

        finished = time.monotonic()
        wrote = "".join(answer)
        self._set(key, thinking="".join(thinking), answer=wrote)

        if error is not None:
            yield self._set(
                key, state="failed", said=failed(error, run).error or str(error)
            )
            return

        output = result.output if result is not None else None
        tokens = result.usage.output_tokens if result is not None else 0
        thought = bool("".join(thinking).strip())

        if resolution.coercion is not None:
            written = json.dumps(output, indent=2, ensure_ascii=False)
            self._set(key, answer=written)

        match key:
            case "answers":
                yield self._answered(
                    resolution, thought, wrote, sent, first, finished, tokens
                )
            case "off":
                why = unheeded("off", thought)
                yield self._set(
                    key,
                    state="failed" if why else "passed",
                    said=why or gettext("no thinking came back"),
                )
            case "tools":
                yield self._called(run, wrote)
            case _:
                yield self._held(key, resolution, output)

    def _answered(
        self,
        resolution: Resolution,
        thought: bool,
        wrote: str,
        sent: float,
        first: float | None,
        finished: float,
        tokens: int,
    ) -> Checked:
        why = unheeded(resolution.reasoning.intent, thought)

        if not wrote.strip():
            return self._set(
                "answers", state="failed", said=gettext("it answered nothing")
            )

        timing = gettext("the first token after %(first).1f s") % {
            "first": (first or finished) - sent
        }

        if tokens and first is not None and finished > first:
            timing += ", " + gettext(
                "%(tokens)d tokens in %(took).1f s, %(rate).0f a second"
            ) % {
                "tokens": tokens,
                "took": finished - first,
                "rate": tokens / (finished - first),
            }

        if why:
            return self._set("answers", state="failed", said=f"{why}; {timing}")

        return self._set("answers", state="passed", said=timing)

    def _held(self, key: str, resolution: Resolution, output: Any) -> Checked:
        if holds(resolution, output):
            return self._set(
                key, state="passed", said=gettext("the answer holds to the schema")
            )

        coercion = resolution.coercion
        assert coercion is not None

        return self._set(
            key,
            state="failed",
            said=gettext("the answer doesn't hold to the schema: %(why)s")
            % {"why": invalid(coercion.schema, output)},
        )

    def _called(self, run: Run, wrote: str) -> Checked:
        calls = [
            part
            for message in run.new_messages
            if isinstance(message, ModelResponse)
            for part in message.parts
            if isinstance(part, ToolCallPart) and part.tool_name == PROBE.name
        ]
        returns = [
            part
            for message in run.new_messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, ToolReturnPart) and part.tool_name == PROBE.name
        ]

        if not calls:
            return self._set(
                "tools",
                state="failed",
                said=gettext("it answered without calling %(tool)s")
                % {"tool": PROBE.name},
            )

        call = calls[0]
        returned = str(returns[0].content) if returns else ""
        arguments = ", ".join(f"{k}={v}" for k, v in call.args_as_dict().items())
        said = {"tool": call.tool_name, "arguments": arguments, "returned": returned}

        if returned.startswith("invalid arguments: "):
            return self._set(
                "tools",
                state="failed",
                said=gettext("%(tool)s(%(arguments)s): %(returned)s") % said,
            )

        if not wrote.strip():
            return self._set(
                "tools",
                state="failed",
                said=gettext(
                    "%(tool)s(%(arguments)s) returned %(returned)s, and it answered nothing"
                )
                % said,
            )

        return self._set(
            "tools",
            state="passed",
            said=gettext(
                "%(tool)s(%(arguments)s) returned %(returned)s, and it answered"
            )
            % said,
        )


def _unsendable(stack: StackBranchOut) -> str | None:
    details = stack.details

    if details.api is None:
        return gettext("not tried: the stack names no API")

    if details.api != "vllm":
        return gettext("not tried: the portal sends to vLLM only, not %(api)s") % {
            "api": details.api
        }

    if details.endpoint is None:
        return gettext("not tried: the stack names no endpoint")

    if details.served_name is None:
        return gettext("not tried: the stack names no served name")

    return None


def _listed(response: Any, took: float) -> tuple[str, list[dict[str, Any]] | None]:
    status = response.status_code

    if status in (401, 403):
        return gettext("refuses the credential: HTTP %(status)d") % {
            "status": status
        }, None

    if status != 200:
        return gettext("answers GET /models with HTTP %(status)d") % {
            "status": status
        }, None

    try:
        listed = response.json()["data"]
    except (ValueError, KeyError, TypeError):
        listed = None

    if not isinstance(listed, list):
        return gettext("answers GET /models with no list of models"), None

    return (
        gettext("answers in %(took)d ms") % {"took": round(took * 1000)},
        [model for model in listed if isinstance(model, dict)],
    )


async def _version(client: httpx2.AsyncClient, base: str) -> str | None:
    if not base.endswith("/v1"):
        return None

    try:
        response = await client.get(f"{base.removesuffix('/v1')}/version")
        version = (
            response.json().get("version") if response.status_code == 200 else None
        )
    except (httpx2.HTTPError, ValueError, AttributeError):
        return None

    return version if isinstance(version, str) else None
