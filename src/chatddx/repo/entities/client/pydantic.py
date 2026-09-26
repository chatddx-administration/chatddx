from pydantic import Field

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


class ClientDetails(Details):
    rev: str | None = None
    packages: dict[str, str] = Field(default_factory=dict)


class ClientTrailBase(BaseTrail):
    build: StorePath | None = None


class ClientTrailIn(ClientTrailBase, TrailIn):
    pass


class ClientTrailRef(TrailRef, ClientTrailBase):
    pass


class ClientTrailOut(ClientTrailBase, TrailOut):
    pass


class ClientBranchDetails(BranchDetails, ClientDetails):
    pass


class ClientBranchDetailsPatch(BranchDetailsPatch, ClientDetails):
    pass


class ClientBranchIn(BaseBranch[ClientTrailIn], ClientBranchDetails):
    pass


class ClientBranchOut(BranchOut[ClientTrailOut, ClientDetails]):
    pass


class ClientFormDataIn(ClientTrailBase, BaseFormDataIn):
    rev: str | None = None
    packages: dict[str, str] = Field(default_factory=dict)


class ClientFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    build: str | None
    rev: str | None
    packages: dict[str, str]
