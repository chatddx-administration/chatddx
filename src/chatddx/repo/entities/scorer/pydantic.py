from typing import Annotated, Literal

from pydantic import Field, JsonValue

from chatddx.repo.entities.case.pydantic import TargetKind
from chatddx.repo.entities.output.pydantic import View
from chatddx.repo.families import (
    BaseTrail,
    BranchDetails,
    BranchDetailsPatch,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
)
from chatddx.repo.families.fields import EntryPoint, distinct

type Metric = Literal["mean", "stderr", "std", "var"]


class ScorerDetails(Details):
    metrics: Annotated[list[Metric], distinct()] = Field(
        default_factory=lambda: ["mean", "stderr"]
    )


class ScorerTrailBase(BaseTrail):
    function: EntryPoint
    view: View
    target_kind: TargetKind | None = None
    args: dict[str, JsonValue] = Field(default_factory=dict)


class ScorerTrailIn(ScorerTrailBase, TrailIn):
    pass


class ScorerTrailOut(ScorerTrailBase, TrailOut):
    pass


class ScorerBranchDetails(BranchDetails, ScorerDetails):
    pass


class ScorerBranchDetailsPatch(BranchDetailsPatch, ScorerDetails):
    pass


class ScorerBranchOut(BranchOut[ScorerTrailOut, ScorerDetails]):
    pass
