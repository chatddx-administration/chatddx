"""
A scorer: what a run's answer comes to, by a function of chatddx's own, the
view of the output it reads, and the kind of target it holds that view to
(datamodel.md §7).

It is inspect's scorer spec. The function is the scorer's name, and the view,
the target kind and the arguments are its options. What can change a score is
content, so a score cites exactly what made it. How scores are summed up
changes none of them, so the metrics are details.

The function runs as a tool's does (`chatddx.runtime.implementation`): only
from chatddx's own scorer files, loaded afresh, and each score records the git
blob of the file that scored. The view and the target kind are fields of their
own rather than arguments, since pairing a scorer with a run reads them.
"""

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
    # keyword arguments the function takes beside the view's items and the
    # target
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
