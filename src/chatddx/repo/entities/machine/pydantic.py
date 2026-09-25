from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from chatddx.core.fields import CoercedStr
from chatddx.repo.families import (
    BaseBranch,
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchDetails,
    BranchDetailsPatch,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
    TrailRef,
)


class GPU(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    # as `nvidia-smi` names it: "NVIDIA GeForce RTX 3070"
    model: str
    memory_mib: int = Field(gt=0)
    uuid: Annotated[str, StringConstraints(pattern=r"^GPU-[0-9a-f-]{36}$")]


class MachineSpecs(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    gpus: list[GPU] = Field(default_factory=list)
    cpu: str | None = None
    ram_gib: int | None = Field(default=None, gt=0)
    location: str | None = None


class MachineDetails(Details):
    unreliable: bool = False
    specs: MachineSpecs | None = None


class MachineTrailBase(BaseTrail):
    machine_id: UUID


class MachineTrailIn(MachineTrailBase, TrailIn):
    pass


class MachineTrailRef(TrailRef, MachineTrailBase):
    pass


class MachineTrailOut(MachineTrailBase, TrailOut):
    pass


class MachineBranchDetails(BranchDetails, MachineDetails):
    pass


class MachineBranchDetailsPatch(BranchDetailsPatch, MachineDetails):
    pass


class MachineBranchIn(BaseBranch[MachineTrailIn], MachineBranchDetails):
    pass


class MachineBranchOut(BranchOut[MachineTrailOut, MachineDetails]):
    pass


class MachineFormDataIn(MachineTrailBase, BaseFormDataIn):
    unreliable: bool = False
    specs: MachineSpecs | None = None


class MachineFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    machine_id: UUID
    unreliable: bool
    specs: MachineSpecs | None
