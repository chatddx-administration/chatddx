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

type Effort = Literal[
    "default", "off", "on", "minimal", "low", "medium", "high", "xhigh"
]

type Intent = Literal["off", "on", "minimal", "low", "medium", "high", "xhigh"]

INTENTS: tuple[Intent, ...] = get_args(Intent.__value__)

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
