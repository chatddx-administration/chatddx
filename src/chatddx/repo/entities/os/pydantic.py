"""
An operating system: a thing, identified by one field.

The identity is the system's top-level store path, what /run/current-system
points to. It is exactly the closure that runs, the vLLM service included,
where the flake revision would name source rather than a system, and none at
all for a dirty tree (data-generation.md §1). The revision is kept as
description.

A NixOS container has a system of its own but runs on its host's kernel and
NVIDIA driver, so the host's system is registered as an OS too, and a stack
points at both.
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

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
from chatddx.repo.families.fields import StorePath


class OsSpecs(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    hostname: str | None = None
    # none for a container: it runs on its host's
    kernel: str | None = None
    nvidia_driver: str | None = None
    nixpkgs_rev: str | None = None


class OsDetails(Details):
    flake_rev: str | None = None
    specs: OsSpecs | None = None


class OsTrailBase(BaseTrail):
    toplevel: StorePath


class OsTrailSchema(OsTrailBase, TrailSchema):
    pass


class OsTrailSchemaRef(TrailSchemaRef, OsTrailBase):
    pass


class OsTrailSpec(OsTrailBase, TrailSpec):
    pass


class OsBranchDetails(BranchSchemaDetails, OsDetails):
    pass


class OsBranchDetailsPatch(BranchDetailsPatch, OsDetails):
    pass


class OsBranchSchema(BaseBranch[OsTrailSchema], OsBranchDetails):
    pass


class OsBranchSpec(BranchSpec[OsTrailSpec, OsDetails]):
    pass


class OsFormDataIn(OsTrailBase, BaseFormDataIn):
    flake_rev: str | None = None
    specs: OsSpecs | None = None


class OsFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    toplevel: str
    flake_rev: str | None
    specs: OsSpecs | None
