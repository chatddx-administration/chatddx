"""
Coercion: a request-time slice, split from the output (new-datamodel.md §2).

The output's schema says what is asked for; the mode says how the LLM is
held to it, and it goes with the LLM's capabilities rather than with the
schema. Split, a batch crosses the two instead of copying a schema once per
mode.

Whether the LLM is shown the schema goes with the mode too. Tool mode shows
it anyway, as the final-result tool's parameters, and prompted mode is
nothing but showing it. `schema_prompt` is chatddx's own text for showing
it, placed through the instruction's `schema_prompt` slot; null means the
schema isn't shown. `tool_description` is chatddx's own text for the tool
the answer is given through, in tool mode. `auto` is resolved from the
LLM's facts before anything is built from it.
"""

from typing import Literal

from pydantic import Field, model_validator

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
from chatddx.repo.templates import placements

type CoercionMode = Literal["native", "tool", "prompted", "auto"]

# every mode but `auto`, which stands for one of them: what an LLM's facts
# say works
type Mode = Literal["native", "tool", "prompted"]

# the instruction's variable the schema prompt fills
SLOT = "schema_prompt"


class CoercionTrailBase(BaseTrail):
    mode: CoercionMode
    # a template that places `{{schema}}`, the output's schema as JSON
    schema_prompt: str | None = None
    # what the tool the answer is given through is said to be, in tool mode:
    # text the LLM reads
    tool_description: str | None = None

    @model_validator(mode="after")
    def _the_prompt_shows_the_schema(self):
        if self.mode == "prompted" and self.schema_prompt is None:
            raise ValueError(
                "prompted mode is nothing but showing the schema: it needs a schema_prompt"
            )

        if self.schema_prompt is not None:
            placed = placements(self.schema_prompt)

            if placed.names != frozenset({"schema"}) or placed.conditions:
                raise ValueError(
                    "a schema prompt places {{schema}}, and nothing else; "
                    + f"this one places {sorted(placed.names) or 'nothing'}"
                )

        return self

    @model_validator(mode="after")
    def _a_tool_is_said_to_be_something(self):
        if self.mode == "tool" and self.tool_description is None:
            raise ValueError(
                "tool mode gives the answer through a tool the LLM reads a "
                + "description of: it needs a tool_description"
            )

        if self.tool_description is not None:
            if self.mode not in ("tool", "auto"):
                raise ValueError(
                    "a tool description is for tool mode, or for auto, which may "
                    + "resolve to it"
                )

            if placements(self.tool_description).names:
                raise ValueError("a tool description places nothing")

        return self


class CoercionTrailIn(CoercionTrailBase, TrailIn):
    pass


class CoercionTrailRef(TrailRef, CoercionTrailBase):
    pass


class CoercionTrailOut(CoercionTrailBase, TrailOut):
    pass


class CoercionBranchIn(BranchIn[CoercionTrailIn]):
    pass


class CoercionBranchOut(BranchOut[CoercionTrailOut, Details]):
    pass


class CoercionFormDataIn(CoercionTrailBase, BaseFormDataIn):
    pass


class CoercionFormDataOut(CoercionTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
