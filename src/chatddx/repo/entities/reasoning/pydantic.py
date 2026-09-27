from typing import Literal, get_args

from pydantic import PositiveInt, model_validator

from chatddx.repo.families import (
    BaseTrail,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
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


class ReasoningTrailOut(ReasoningTrailBase, TrailOut):
    pass


class ReasoningBranchOut(BranchOut[ReasoningTrailOut, Details]):
    pass
