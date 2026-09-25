"""
Reasoning: a request-time slice (datamodel.md §4).

A variation is an effort, and optionally a token budget. It states an intent,
and an LLM's facts translate it: into a request fragment, into another
intent it collapses into, or into a refusal. Qwen3 has no effort levels, so
every effort is "on" there; gpt-oss can't stop reasoning, so "off" is refused.
`default` is the LLM's own effort, which resolution looks up and writes out.
"""

from typing import Literal, get_args

from pydantic import Field, PositiveInt, model_validator

from chatddx.core.fields import CoercedStr
from chatddx.repo.families import (
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchIn,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
    TrailRef,
)

# pydantic-ai's ThinkingLevel, plus `default` for the LLM's own
type Effort = Literal[
    "default", "off", "on", "minimal", "low", "medium", "high", "xhigh"
]

# every effort but `default`, which stands for one of them: what an LLM's
# facts translate
type Intent = Literal["off", "on", "minimal", "low", "medium", "high", "xhigh"]

INTENTS: tuple[Intent, ...] = get_args(Intent.__value__)

# The request fields the reasoning slice writes, whatever an LLM's facts
# have it write. No other slice writes them (datamodel.md §5).
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


class ReasoningTrailIn(ReasoningTrailBase, TrailIn):
    pass


class ReasoningTrailRef(TrailRef, ReasoningTrailBase):
    pass


class ReasoningTrailOut(ReasoningTrailBase, TrailOut):
    pass


class ReasoningBranchIn(BranchIn[ReasoningTrailIn]):
    pass


class ReasoningBranchOut(BranchOut[ReasoningTrailOut, Details]):
    pass


class ReasoningFormDataIn(ReasoningTrailBase, BaseFormDataIn):
    pass


class ReasoningFormDataOut(ReasoningTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
