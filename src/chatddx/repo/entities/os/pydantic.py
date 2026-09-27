from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from chatddx.repo.families import (
    BaseTrail,
    BranchDetails,
    BranchDetailsPatch,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
)
from chatddx.repo.families.fields import StorePath


class OsSpecs(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    hostname: str | None = None
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


class OsTrailOut(OsTrailBase, TrailOut):
    pass


class OsBranchDetails(BranchDetails, OsDetails):
    pass


class OsBranchDetailsPatch(BranchDetailsPatch, OsDetails):
    pass


class OsBranchOut(BranchOut[OsTrailOut, OsDetails]):
    pass
