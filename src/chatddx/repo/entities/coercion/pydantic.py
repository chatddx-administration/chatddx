"""
Coercion: a request-time slice, split from the output (new-datamodel.md §2).

The output's schema says what is asked for; the mode says how the model is
held to it, and it goes with the model's capabilities rather than with the
schema. Split, a batch crosses the two instead of copying a schema once per
mode.

Whether the model is shown the schema goes with the mode too. Tool mode shows
it anyway, as the final-result tool's parameters, and prompted mode is
nothing but showing it. `schema_prompt` is chatddx's own text for showing
it, placed through the instruction's `schema_prompt` slot; null means the
schema isn't shown. `auto` is resolved from the model's facts before
anything is built from it.
"""

from typing import Literal

from pydantic import Field, model_validator

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
from chatddx.repo.templates import placements

type CoercionMode = Literal["native", "tool", "prompted", "auto"]

# every mode but `auto`, which stands for one of them: what a model's facts
# say works
type Mode = Literal["native", "tool", "prompted"]

# the instruction's variable the schema prompt fills
SLOT = "schema_prompt"


class CoercionTrailBase(BaseTrail):
    mode: CoercionMode
    # a template that places `{{schema}}`, the output's schema as JSON
    schema_prompt: str | None = None

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


class CoercionTrailSchema(CoercionTrailBase, TrailSchema):
    pass


class CoercionTrailSchemaRef(TrailSchemaRef, CoercionTrailBase):
    pass


class CoercionTrailSpec(CoercionTrailBase, TrailSpec):
    pass


class CoercionBranchSchema(BranchSchema[CoercionTrailSchema]):
    pass


class CoercionBranchSpec(BranchSpec[CoercionTrailSpec, Details]):
    pass


class CoercionFormDataIn(CoercionTrailBase, BaseFormDataIn):
    pass


class CoercionFormDataOut(CoercionTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
