"""
Reasoning: a request-time slice (new-datamodel.md §2).

A variation is an effort, and optionally a token budget. It states an intent,
and a model's facts translate it: into a request fragment, into another
intent it collapses into, or into a refusal. Qwen3 has no effort levels, so
every effort is "on" there; gpt-oss can't stop reasoning, so "off" is refused.
`default` is the model's own effort, which resolution looks up and writes out.
"""

from typing import Literal, get_args

from pydantic import Field, PositiveInt, model_validator

from chatddx.core.fields import CoercedStr
from chatddx.repo.families import (
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchSchema,
    BranchSpec,
    Details,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)

# pydantic-ai's ThinkingLevel, plus `default` for the model's own
type Effort = Literal[
    "default", "off", "on", "minimal", "low", "medium", "high", "xhigh"
]

# every effort but `default`, which stands for one of them: what a model's
# facts translate
type Intent = Literal["off", "on", "minimal", "low", "medium", "high", "xhigh"]

INTENTS: tuple[Intent, ...] = get_args(Intent.__value__)

# The request fields the reasoning slice writes, whatever a model's facts
# have it write. No other slice writes them (new-datamodel.md §3).
REASONING_WRITES = frozenset(
    {
        "chat_template_kwargs",
        "reasoning_effort",
        "thinking_token_budget",
    }
)


class ReasoningTrailBase(BaseTrail):
    effort: Effort
    budget: PositiveInt | None = None

    @model_validator(mode="after")
    def _a_budget_is_for_reasoning(self):
        if self.effort == "off" and self.budget is not None:
            raise ValueError("a token budget for reasoning that is off")

        return self


class ReasoningTrailSchema(ReasoningTrailBase, TrailSchema):
    pass


class ReasoningTrailSchemaRef(TrailSchemaRef, ReasoningTrailBase):
    pass


class ReasoningTrailSpec(ReasoningTrailBase, TrailSpec):
    pass


class ReasoningBranchSchema(BranchSchema[ReasoningTrailSchema]):
    pass


class ReasoningBranchSpec(BranchSpec[ReasoningTrailSpec, Details]):
    pass


class ReasoningFormDataIn(ReasoningTrailBase, BaseFormDataIn):
    pass


class ReasoningFormDataOut(ReasoningTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
