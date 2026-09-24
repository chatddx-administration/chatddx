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
    BranchDetails,
    BranchDetailsPatch,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
    TrailRef,
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


class OsTrailIn(OsTrailBase, TrailIn):
    pass


class OsTrailRef(TrailRef, OsTrailBase):
    pass


class OsTrailOut(OsTrailBase, TrailOut):
    pass


class OsBranchDetails(BranchDetails, OsDetails):
    pass


class OsBranchDetailsPatch(BranchDetailsPatch, OsDetails):
    pass


class OsBranchIn(BaseBranch[OsTrailIn], OsBranchDetails):
    pass


class OsBranchOut(BranchOut[OsTrailOut, OsDetails]):
    pass


class OsFormDataIn(OsTrailBase, BaseFormDataIn):
    flake_rev: str | None = None
    specs: OsSpecs | None = None


class OsFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    toplevel: str
    flake_rev: str | None
    specs: OsSpecs | None
