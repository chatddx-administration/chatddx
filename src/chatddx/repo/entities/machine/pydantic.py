"""
A machine: a thing, identified by one field.

The machine id is assigned when a physical machine is registered, and any
change to its hardware makes a new machine. Everything else about it is
description. The GPU UUIDs it lists back a check rather than an identity: a
host reports its GPUs (`nvidia-smi -L`), and a run on a machine whose GPUs
don't match its registration is flagged (data-generation.md §1).

A cloud provider is a machine too, marked unreliable: nothing below its
requests can be checked.
"""

from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from chatddx.core.fields import CoercedStr
from chatddx.repo.families import (
    BaseBranch,
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchDetailsPatch,
    BranchSchemaDetails,
    BranchSpec,
    Details,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
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


class MachineTrailSchema(MachineTrailBase, TrailSchema):
    pass


class MachineTrailSchemaRef(TrailSchemaRef, MachineTrailBase):
    pass


class MachineTrailSpec(MachineTrailBase, TrailSpec):
    pass


class MachineBranchDetails(BranchSchemaDetails, MachineDetails):
    pass


class MachineBranchDetailsPatch(BranchDetailsPatch, MachineDetails):
    pass


class MachineBranchSchema(BaseBranch[MachineTrailSchema], MachineBranchDetails):
    pass


class MachineBranchSpec(BranchSpec[MachineTrailSpec, MachineDetails]):
    pass


class MachineFormDataIn(MachineTrailBase, BaseFormDataIn):
    unreliable: bool = False
    specs: MachineSpecs | None = None


class MachineFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    machine_id: UUID
    unreliable: bool
    specs: MachineSpecs | None
