"""
Resolution: a cell, a configuration joined to a stack, made into one request
or refused with its reasons (new-datamodel.md §2, §9).

Each slice's variation states an intent, and the facts of the stack's model
realize it. The slices are resolved in the order each reads the ones before
it: the model, reasoning, sampling, output and coercion, the instruction
with its slots filled, then the toolset. The case is left out: a cell is
resolved once, and each trial renders it with a case of its own.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import JsonValue
from pydantic_ai import TemplateStr

from chatddx.repo.entities.coercion.pydantic import (
    SLOT as SCHEMA_PROMPT,
    CoercionMode,
    CoercionTrailBase,
    Mode,
)
from chatddx.repo.entities.instruction.pydantic import InstructionTrailBase
from chatddx.repo.entities.model.pydantic import (
    BudgetFact,
    ModeFact,
    ModelFacts,
    Refusal,
)
from chatddx.repo.entities.output.pydantic import (
    SLOT as OUTPUT_GUIDANCE,
    OutputTrailBase,
)
from chatddx.repo.entities.reasoning.pydantic import Effort, Intent, ReasoningTrailBase
from chatddx.repo.entities.sampling.pydantic import SamplingFields, SamplingTrailBase
from chatddx.repo.entities.serving.pydantic import Requirement, ServingTrailBase
from chatddx.repo.entities.stack.pydantic import StackDetails
from chatddx.repo.entities.tool.pydantic import ToolTrailBase
from chatddx.repo.entities.toolset.pydantic import SLOT as TOOL_GUIDANCE

type Slice = Literal[
    "model", "reasoning", "sampling", "output", "coercion", "instruction", "toolset"
]


class Toolset(Protocol):
    @property
    def guidance(self) -> str | None: ...
    @property
    def tools(self) -> Sequence[ToolTrailBase]: ...


class Configuration(Protocol):
    @property
    def instruction(self) -> InstructionTrailBase: ...
    @property
    def output(self) -> OutputTrailBase: ...
    @property
    def coercion(self) -> CoercionTrailBase: ...
    @property
    def reasoning(self) -> ReasoningTrailBase: ...
    @property
    def sampling(self) -> SamplingTrailBase: ...
    @property
    def toolset(self) -> Toolset | None: ...


@dataclass(frozen=True)
class Slices:
    """A configuration's variations with any of them swapped for another."""

    instruction: InstructionTrailBase
    output: OutputTrailBase
    coercion: CoercionTrailBase
    reasoning: ReasoningTrailBase
    sampling: SamplingTrailBase
    toolset: Toolset | None


@dataclass(frozen=True)
class SliceRefusal:
    slice: Slice
    reason: str
    kind: Literal["refused", "later"] = "refused"


@dataclass(frozen=True)
class Reasoning:
    effort: Effort
    intent: Intent
    writes: dict[str, JsonValue]


@dataclass(frozen=True)
class Sampling:
    source: str
    writes: dict[str, JsonValue]


@dataclass(frozen=True)
class Coercion:
    requested: CoercionMode
    mode: Mode
    schema: dict[str, JsonValue]
    sent: dict[str, JsonValue]
    tool_description: str | None
    note: str | None


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, JsonValue]


class CellRefused(Exception):
    """A cell refused, with what its other slices resolve to regardless."""

    def __init__(
        self,
        refusals: list[SliceRefusal],
        reasoning: Reasoning | None,
        sampling: Sampling | None,
        coercion: Coercion | None,
        tools: list[Tool],
        slots: dict[str, str],
    ):
        super().__init__("; ".join(f"{r.slice}: {r.reason}" for r in refusals))
        self.refusals: list[SliceRefusal] = refusals
        self.reasoning: Reasoning | None = reasoning
        self.sampling: Sampling | None = sampling
        self.coercion: Coercion | None = coercion
        self.tools: list[Tool] = tools
        self.slots: dict[str, str] = slots


@dataclass(frozen=True)
class Resolution:
    endpoint: str
    served_name: str
    credential: str | None
    profile: dict[str, JsonValue]
    reasoning: Reasoning
    sampling: Sampling
    output: OutputTrailBase
    coercion: Coercion | None
    tools: list[Tool]
    instruction: InstructionTrailBase
    slots: dict[str, str]

    @property
    def fields(self) -> dict[str, JsonValue]:
        """What the request states beside its messages and its model."""
        return self.reasoning.writes | self.sampling.writes

    def render(self, case: str) -> tuple[str, str]:
        """The system and user messages, with `case` placed."""
        variables: dict[str, str | None] = {
            name: None for name in self.instruction.variables
        }
        variables |= self.slots | {"case": case}

        return (
            TemplateStr(self.instruction.system).render(variables),
            TemplateStr(self.instruction.user).render(variables),
        )


def resolve(
    configuration: Configuration,
    stack: StackDetails,
    facts: ModelFacts,
    serving: ServingTrailBase | None,
) -> Resolution:
    refusals: list[SliceRefusal] = []

    if stack.api is None:
        refusals.append(SliceRefusal("model", "the stack names no API"))
    elif stack.api != "vllm":
        refusals.append(
            SliceRefusal(
                "model", f"the repl sends to vLLM only, not {stack.api}", "later"
            )
        )

    if stack.endpoint is None:
        refusals.append(SliceRefusal("model", "the stack names no endpoint"))

    if stack.served_name is None:
        refusals.append(SliceRefusal("model", "the stack names no served name"))

    reasoning, sampling, found = realize(
        configuration.reasoning, configuration.sampling, facts, serving
    )
    refusals += found
    coercion, slots = _output(configuration, reasoning, facts, serving, refusals)
    tools = _toolset(configuration.toolset, serving, refusals)

    if configuration.toolset and configuration.toolset.guidance is not None:
        slots[TOOL_GUIDANCE] = configuration.toolset.guidance

    _placed(configuration.instruction, slots, refusals)

    if refusals:
        raise CellRefused(refusals, reasoning, sampling, coercion, tools, slots)

    assert stack.endpoint and stack.served_name and reasoning and sampling

    return Resolution(
        endpoint=str(stack.endpoint),
        served_name=stack.served_name,
        credential=stack.credential,
        profile=facts.profile,
        reasoning=reasoning,
        sampling=sampling,
        output=configuration.output,
        coercion=coercion,
        tools=tools,
        instruction=configuration.instruction,
        slots=slots,
    )


def realize(
    reasoning: ReasoningTrailBase,
    sampling: SamplingTrailBase | None,
    facts: ModelFacts,
    serving: ServingTrailBase | None,
) -> tuple[Reasoning | None, Sampling | None, list[SliceRefusal]]:
    """
    A reasoning variation on a model, and the sampling it pulls in. The two
    are resolved together: sampling can default to what the facts recommend
    for the mode reasoning resolves to, and a budget spends max_tokens.
    """
    refusals: list[SliceRefusal] = []
    provided = serving.provides() if serving else frozenset[Requirement]()

    realized = _reasoning(reasoning, facts, provided, refusals)
    pulled = _sampling(sampling, facts, realized, refusals) if sampling else None

    if realized and pulled:
        _budget_fits(reasoning, pulled, refusals)

    return realized, pulled, refusals


def _reasoning(
    variation: ReasoningTrailBase,
    facts: ModelFacts,
    provided: frozenset[Requirement],
    refusals: list[SliceRefusal],
) -> Reasoning | None:
    effort = variation.effort
    resolved = facts.reasoning.resolve(effort)

    if resolved is None:
        missing = (
            "no default effort" if effort == "default" else f"nothing on '{effort}'"
        )
        refusals.append(SliceRefusal("reasoning", f"the model's facts say {missing}"))
        return None

    intent, fact = resolved

    if isinstance(fact, Refusal):
        through = "" if intent == effort else f"it ends at '{intent}': "
        refusals.append(SliceRefusal("reasoning", f"{through}{fact.refused}"))
        return None

    writes = dict(fact)

    if variation.budget is not None:
        budget = facts.reasoning.budget

        match budget:
            case None:
                refusals.append(
                    SliceRefusal(
                        "reasoning", "the model's facts say nothing on a budget"
                    )
                )
            case Refusal():
                refusals.append(SliceRefusal("reasoning", budget.refused))
            case BudgetFact():
                missing = [need for need in budget.needs if need not in provided]

                if missing:
                    refusals.append(
                        SliceRefusal(
                            "reasoning",
                            f"a budget needs {_listed(missing)}, which the serving "
                            + "doesn't provide",
                        )
                    )
                else:
                    writes[budget.field] = variation.budget

    return Reasoning(effort, intent, writes)


def _sampling(
    variation: SamplingTrailBase,
    facts: ModelFacts,
    reasoning: Reasoning | None,
    refusals: list[SliceRefusal],
) -> Sampling | None:
    match variation.defaults:
        case "model":
            base = facts.sampling.generation_config
            source = "the model's generation config"

            if base is None:
                refusals.append(
                    SliceRefusal(
                        "sampling",
                        "the model's facts say nothing on its generation config",
                    )
                )
                return None
        case "recommended":
            if reasoning is None:
                return None

            base = facts.sampling.recommended.get(reasoning.intent)
            source = f"recommended for '{reasoning.intent}'"

            if base is None:
                refusals.append(
                    SliceRefusal(
                        "sampling",
                        f"the model's facts recommend nothing for '{reasoning.intent}'",
                    )
                )
                return None

    explicit = {
        name: getattr(variation, name)
        for name in SamplingFields.model_fields
        if getattr(variation, name) is not None
    }

    return Sampling(source, base.model_dump(exclude_none=True) | explicit)


def _budget_fits(
    variation: ReasoningTrailBase,
    sampling: Sampling,
    refusals: list[SliceRefusal],
) -> None:
    max_tokens = sampling.writes.get("max_tokens")

    if (
        variation.budget is not None
        and isinstance(max_tokens, int)
        and variation.budget >= max_tokens
    ):
        refusals.append(
            SliceRefusal(
                "reasoning",
                f"a budget of {variation.budget} doesn't fit in max_tokens "
                + f"{max_tokens}",
            )
        )


def _output(
    configuration: Configuration,
    reasoning: Reasoning | None,
    facts: ModelFacts,
    serving: ServingTrailBase | None,
    refusals: list[SliceRefusal],
) -> tuple[Coercion | None, dict[str, str]]:
    """How the output is held to its schema, and the slots the two fill."""
    output = configuration.output
    variation = configuration.coercion
    coercion: Coercion | None = None
    slots: dict[str, str] = {}

    if output.guidance is not None:
        slots[OUTPUT_GUIDANCE] = output.guidance

    if output.schema is not None:
        coercion = _coercion(
            variation, output.schema, reasoning, facts, serving, refusals
        )

        if coercion and variation.schema_prompt is not None:
            schema = json.dumps(output.schema, indent=2, ensure_ascii=False)
            slots[SCHEMA_PROMPT] = TemplateStr(variation.schema_prompt).render(
                {"schema": schema}
            )

    return coercion, slots


def _toolset(
    toolset: Toolset | None,
    serving: ServingTrailBase | None,
    refusals: list[SliceRefusal],
) -> list[Tool]:
    """The tools the model is offered, as the request carries them."""
    if toolset is None:
        return []

    provided = serving.provides() if serving else frozenset[Requirement]()

    if "tool_call_parser" not in provided:
        refusals.append(
            SliceRefusal(
                "toolset",
                "tools need a tool call parser, which the serving doesn't provide",
            )
        )

    tools: list[Tool] = []

    for tool in toolset.tools:
        try:
            parameters = inlined(tool.parameters)
        except ValueError as e:
            refusals.append(
                SliceRefusal("toolset", f"'{tool.name}' can't be sent: {e}")
            )
            continue

        tools.append(Tool(tool.name, tool.description, parameters))

    return tools


FILLERS = {
    OUTPUT_GUIDANCE: "output",
    SCHEMA_PROMPT: "coercion",
    TOOL_GUIDANCE: "toolset",
}


def _placed(
    instruction: InstructionTrailBase,
    slots: dict[str, str],
    refusals: list[SliceRefusal],
) -> None:
    for slot in slots:
        if slot not in instruction.variables:
            refusals.append(
                SliceRefusal(
                    "instruction",
                    f"it doesn't place '{slot}', which the {FILLERS[slot]} fills",
                )
            )


def _coercion(
    variation: CoercionTrailBase,
    schema: dict[str, JsonValue],
    reasoning: Reasoning | None,
    facts: ModelFacts,
    serving: ServingTrailBase | None,
    refusals: list[SliceRefusal],
) -> Coercion | None:
    mode = facts.coercion.default if variation.mode == "auto" else variation.mode

    if mode is None:
        refusals.append(
            SliceRefusal("coercion", "the model's facts name no mode for 'auto'")
        )
        return None

    through = "" if mode == variation.mode else f"it ends at '{mode}': "
    fact: ModeFact | Refusal | None = getattr(facts.coercion, mode)

    match fact:
        case None:
            refusals.append(
                SliceRefusal(
                    "coercion", f"{through}the model's facts say nothing on '{mode}'"
                )
            )
        case Refusal():
            refusals.append(SliceRefusal("coercion", f"{through}{fact.refused}"))
        case ModeFact():
            provided = serving.provides() if serving else frozenset[Requirement]()
            reasons = reasoning is None or reasoning.intent != "off"
            missing = [
                need
                for need in fact.needs
                if need not in provided and (reasons or need != "reasoning_parser")
            ]

            if missing:
                needed = " and ".join(
                    "a reasoning parser while the model reasons"
                    if need == "reasoning_parser"
                    else "a " + need.replace("_", " ")
                    for need in missing
                )
                refusals.append(
                    SliceRefusal(
                        "coercion",
                        f"{through}'{mode}' needs {needed}, which the serving "
                        + "doesn't provide",
                    )
                )
                return None

            if mode == "tool" and variation.tool_description is None:
                refusals.append(
                    SliceRefusal(
                        "coercion",
                        f"{through}'tool' needs a tool description, which the "
                        + "coercion doesn't give",
                    )
                )
                return None

            try:
                sent = inlined(schema)
            except ValueError as e:
                refusals.append(
                    SliceRefusal("coercion", f"the schema can't be sent: {e}")
                )
                return None

            if sent.get("type") != "object":
                refusals.append(
                    SliceRefusal(
                        "coercion",
                        "the schema can't be sent: an answer is held to an object, "
                        + f"not to {json.dumps(sent.get('type'))}",
                    )
                )
                return None

            return Coercion(
                variation.mode,
                mode,
                schema,
                sent,
                variation.tool_description,
                fact.note,
            )

    return None


def inlined(schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """
    `schema` with each reference in it replaced by what it refers to, and its
    `$defs` dropped: the schema as a request carries it. Done here, it is
    chatddx's to say what the model is held to, not a library's to make of
    the schema. A reference's siblings are kept beside what it refers to.
    """

    def resolve(node: JsonValue, seen: tuple[str, ...]) -> JsonValue:
        match node:
            case {"$ref": str(ref), **siblings}:
                if ref in seen:
                    raise ValueError(f"{ref} refers to itself")

                target = resolve(_pointer(schema, ref), (*seen, ref))
                resolved = {k: resolve(v, seen) for k, v in siblings.items()}

                return (target | resolved) if isinstance(target, dict) else target
            case dict():
                return {k: resolve(v, seen) for k, v in node.items()}
            case list():
                return [resolve(item, seen) for item in node]
            case _:
                return node

    top = {k: v for k, v in schema.items() if k not in ("$defs", "definitions")}
    resolved = resolve(top, ())

    assert isinstance(resolved, dict)
    return resolved


def _pointer(schema: dict[str, JsonValue], ref: str) -> JsonValue:
    if not ref.startswith("#/"):
        raise ValueError(f"{ref} is outside the schema")

    node: JsonValue = schema

    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"{ref} refers to nothing")
        node = node[part]

    return node


def _listed(needs: list[str]) -> str:
    return " and ".join("a " + need.replace("_", " ") for need in needs)
