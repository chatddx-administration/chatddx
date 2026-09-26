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

type SamplingDefaults = Literal["generation_config", "recommended"]


class SamplingFields(BaseModel):
    temperature: Annotated[float, Field(ge=0, le=2)] | None = None
    top_p: Annotated[float, Field(gt=0, le=1)] | None = None
    # -1 turns it off
    top_k: Annotated[int, Field(ge=-1)] | None = None
    max_tokens: PositiveInt | None = None
    presence_penalty: Annotated[float, Field(ge=-2, le=2)] | None = None
    frequency_penalty: Annotated[float, Field(ge=-2, le=2)] | None = None
    stop: list[str] | None = None


class SamplingValues(SamplingFields):
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
