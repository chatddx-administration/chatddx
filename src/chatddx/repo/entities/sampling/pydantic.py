"""
Sampling: a request-time slice (new-datamodel.md §2).

A variation holds explicit values, and says what a value left out means:
`model`, the model's own generation config, or `recommended`, what the
model's facts recommend for the reasoning mode it resolves to. So one
sampling variation fits every reasoning variation. Resolution writes every
value it used into the request, `top_k` included (through `extra_body`).

The seed is not here: it belongs to the trial, one per replicate.
"""

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

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

type SamplingDefaults = Literal["model", "recommended"]


class SamplingFields(BaseModel):
    """The values a sampling variation, or a model's facts, can set."""

    temperature: Annotated[float, Field(ge=0, le=2)] | None = None
    top_p: Annotated[float, Field(gt=0, le=1)] | None = None
    # -1 turns it off
    top_k: Annotated[int, Field(ge=-1)] | None = None
    max_tokens: PositiveInt | None = None
    presence_penalty: Annotated[float, Field(ge=-2, le=2)] | None = None
    frequency_penalty: Annotated[float, Field(ge=-2, le=2)] | None = None
    stop: list[str] | None = None


class SamplingValues(SamplingFields):
    """Sampling values on their own, as a model's facts give them."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class SamplingTrailBase(SamplingFields, BaseTrail):
    defaults: SamplingDefaults


class SamplingTrailIn(SamplingTrailBase, TrailIn):
    pass


class SamplingTrailRef(TrailRef, SamplingTrailBase):
    pass


class SamplingTrailOut(SamplingTrailBase, TrailOut):
    pass


class SamplingBranchIn(BranchIn[SamplingTrailIn]):
    pass


class SamplingBranchOut(BranchOut[SamplingTrailOut, Details]):
    pass


class SamplingFormDataIn(SamplingTrailBase, BaseFormDataIn):
    pass


class SamplingFormDataOut(SamplingTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
