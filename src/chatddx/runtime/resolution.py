"""
Resolution: a cell, a configuration joined to a stack, made into one request
or refused with its reasons (new-datamodel.md §2, §9).

Each slice's variation states an intent, and the facts of the stack's model
realize it. The slices are resolved in the order each reads the ones before
it: the model, reasoning, sampling, output and coercion, the instruction
with its slots filled, then the toolset. The case is left out: a cell is
resolved once, and each trial renders it with a case of its own.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import JsonValue
from pydantic_ai import TemplateStr

from chatddx.repo.entities.coercion.pydantic import CoercionTrailBase
from chatddx.repo.entities.instruction.pydantic import InstructionTrailBase
from chatddx.repo.entities.model.pydantic import BudgetFact, ModelFacts, Refusal
from chatddx.repo.entities.output.pydantic import (
    SLOT as OUTPUT_GUIDANCE,
    OutputTrailBase,
)
from chatddx.repo.entities.reasoning.pydantic import Effort, Intent, ReasoningTrailBase
from chatddx.repo.entities.sampling.pydantic import SamplingFields, SamplingTrailBase
from chatddx.repo.entities.serving.pydantic import Requirement, ServingTrailBase
from chatddx.repo.entities.stack.pydantic import StackDetails
from chatddx.repo.entities.toolset.pydantic import ToolsetTrailBase

type Slice = Literal[
    "model", "reasoning", "sampling", "output", "instruction", "toolset"
]


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
    def toolset(self) -> ToolsetTrailBase | None: ...


@dataclass(frozen=True)
class SliceRefusal:
    slice: Slice
    reason: str
    # `refused`: the stack can't honour the intent; `later`: the repl can't
    # resolve it yet
    kind: Literal["refused", "later"] = "refused"


@dataclass(frozen=True)
class Reasoning:
    effort: Effort
    # what the effort ends at on this model, through the collapses its facts
    # declare
    intent: Intent
    writes: dict[str, JsonValue]


@dataclass(frozen=True)
class Sampling:
    # where the values the variation leaves out come from
    source: str
    writes: dict[str, JsonValue]


class CellRefused(Exception):
    """A cell refused, with what its other slices resolve to regardless."""

    def __init__(
        self,
        refusals: list[SliceRefusal],
        reasoning: Reasoning | None,
        sampling: Sampling | None,
        slots: dict[str, str],
    ):
        super().__init__("; ".join(f"{r.slice}: {r.reason}" for r in refusals))
        self.refusals: list[SliceRefusal] = refusals
        self.reasoning: Reasoning | None = reasoning
        self.sampling: Sampling | None = sampling
        self.slots: dict[str, str] = slots


@dataclass(frozen=True)
class Resolution:
    endpoint: str
    served_name: str
    credential: str | None
    profile: dict[str, JsonValue]
    reasoning: Reasoning
    sampling: Sampling
    instruction: InstructionTrailBase
    # the instruction's slots, as the other slices fill them
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
    provided = serving.provides() if serving else frozenset[Requirement]()

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

    reasoning = _reasoning(configuration.reasoning, facts, provided, refusals)
    sampling = _sampling(configuration.sampling, facts, reasoning, refusals)

    if reasoning and sampling:
        _budget_fits(configuration.reasoning, sampling, refusals)

    slots = _slots(configuration, refusals)

    if refusals:
        raise CellRefused(refusals, reasoning, sampling, slots)

    assert stack.endpoint and stack.served_name and reasoning and sampling

    return Resolution(
        endpoint=str(stack.endpoint),
        served_name=stack.served_name,
        credential=stack.credential,
        profile=facts.profile,
        reasoning=reasoning,
        sampling=sampling,
        instruction=configuration.instruction,
        slots=slots,
    )


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
        through = "" if intent == effort else f", which ends at '{intent}'"
        refusals.append(
            SliceRefusal("reasoning", f"'{effort}'{through} is refused: {fact.refused}")
        )
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
                refusals.append(
                    SliceRefusal("reasoning", f"a budget is refused: {budget.refused}")
                )
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
                # nothing to recommend for: the reasoning is refused already
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


def _slots(
    configuration: Configuration, refusals: list[SliceRefusal]
) -> dict[str, str]:
    output = configuration.output
    slots: dict[str, str] = {}

    if output.schema is not None:
        refusals.append(
            SliceRefusal(
                "output",
                "an output with a schema needs its coercion resolved, which the repl "
                + "doesn't do yet",
                "later",
            )
        )

    # free text: whatever the coercion, it contributes nothing
    if output.guidance is not None:
        slots[OUTPUT_GUIDANCE] = output.guidance

    if configuration.toolset is not None:
        refusals.append(
            SliceRefusal("toolset", "the repl doesn't run tools yet", "later")
        )

    for slot in slots:
        if slot not in configuration.instruction.variables:
            refusals.append(
                SliceRefusal(
                    "instruction",
                    f"it doesn't place '{slot}', which the output fills",
                )
            )

    return slots


def _listed(needs: list[str]) -> str:
    return " and ".join("a " + need.replace("_", " ") for need in needs)
