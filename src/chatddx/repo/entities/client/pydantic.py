from pydantic import Field

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


class ClientDetails(Details):
    rev: str | None = None
    packages: dict[str, str] = Field(default_factory=dict)


class ClientTrailBase(BaseTrail):
    build: StorePath | None = None


class ClientTrailIn(ClientTrailBase, TrailIn):
    pass


class ClientTrailOut(ClientTrailBase, TrailOut):
    pass


class ClientBranchDetails(BranchDetails, ClientDetails):
    pass


class ClientBranchDetailsPatch(BranchDetailsPatch, ClientDetails):
    pass


class ClientBranchOut(BranchOut[ClientTrailOut, ClientDetails]):
    pass
