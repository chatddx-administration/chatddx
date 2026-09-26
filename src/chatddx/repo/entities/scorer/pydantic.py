from typing import Annotated, Literal

from pydantic import Field, JsonValue

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.case.pydantic import TargetKind
from chatddx.repo.entities.output.pydantic import View
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
from chatddx.repo.families.fields import EntryPoint, distinct

# inspect's metrics, by name and formula, over the values a scorer made
type Metric = Literal["mean", "stderr", "std", "var"]


class ScorerDetails(Details):
    metrics: Annotated[list[Metric], distinct()] = Field(
        default_factory=lambda: ["mean", "stderr"]
    )


class ScorerTrailBase(BaseTrail):
    function: EntryPoint
    view: View
    # none for a scorer that needs no target
    target_kind: TargetKind | None = None
    args: dict[str, JsonValue] = Field(default_factory=dict)


class ScorerTrailIn(ScorerTrailBase, TrailIn):
    pass


class ScorerTrailRef(TrailRef, ScorerTrailBase):
    pass


class ScorerTrailOut(ScorerTrailBase, TrailOut):
    pass


class ScorerBranchDetails(BranchDetails, ScorerDetails):
    pass


class ScorerBranchDetailsPatch(BranchDetailsPatch, ScorerDetails):
    pass


class ScorerBranchIn(BaseBranch[ScorerTrailIn], ScorerBranchDetails):
    pass


class ScorerBranchOut(BranchOut[ScorerTrailOut, ScorerDetails]):
    pass


class ScorerFormDataIn(ScorerTrailBase, BaseFormDataIn):
    metrics: Annotated[list[Metric], distinct()] = Field(
        default_factory=lambda: ["mean", "stderr"]
    )


class ScorerFormDataOut(ScorerTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    metrics: list[Metric]
