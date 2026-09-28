from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from chatddx.repo.families import (
    BaseTrail,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
)

type SamplingDefaults = Literal["generation_config", "recommended"]


class SamplingFields(BaseModel):
    temperature: Annotated[float, Field(ge=0, le=2)] | None = None
    top_p: Annotated[float, Field(gt=0, le=1)] | None = None
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


class SamplingTrailOut(SamplingTrailBase, TrailOut):
    pass


class SamplingBranchOut(BranchOut[SamplingTrailOut, Details]):
    pass
