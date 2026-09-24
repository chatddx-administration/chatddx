"""
A case: its payload, as the model receives it through the instruction's
`case` variable, and what it is expected to yield.

The targets are details, not content: they change nothing the model reads,
and the payload is what the case's fingerprint names. Like a model's facts,
they are versioned with the branch, and each score records the row whose
targets it read (new-datamodel.md §11). inspect keeps a sample's target with
the sample, and a case is chatddx's sample. Unlike inspect's one target per
sample, a case has one per kind, and each scorer reads the kind it names.
"""

from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, Field, StringConstraints

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

# What a case can be expected to yield, each read by the scorers that name it
type TargetKind = Literal["diagnosis", "warning", "disposition"]
TARGET_KINDS: tuple[TargetKind, ...] = get_args(TargetKind.__value__)

# The kinds a case may expect none of: a plan that rightly raises no warning.
# `false` says so.
EXPECTS_NONE: frozenset[TargetKind] = frozenset({"warning"})

# text its scorers read, or false where the case expects none
type Target = Annotated[str, StringConstraints(min_length=1)] | Literal[False]


def _none_only_where_expected(
    targets: dict[TargetKind, Target],
) -> dict[TargetKind, Target]:
    refused = sorted(
        kind
        for kind, target in targets.items()
        if target is False and kind not in EXPECTS_NONE
    )

    if refused:
        raise ValueError(
            f"a case expects some {', '.join(refused)}: only "
            + f"{', '.join(sorted(EXPECTS_NONE))} can be false"
        )

    return targets


Targets = Annotated[dict[TargetKind, Target], AfterValidator(_none_only_where_expected)]


class CaseDetails(Details):
    targets: Targets = Field(default_factory=dict)


class CaseTrailBase(BaseTrail):
    payload: str


class CaseTrailIn(CaseTrailBase, TrailIn):
    pass


class CaseTrailRef(TrailRef, CaseTrailBase):
    pass


class CaseTrailOut(CaseTrailBase, TrailOut):
    pass


class CaseBranchDetails(BranchDetails, CaseDetails):
    pass


class CaseBranchDetailsPatch(BranchDetailsPatch, CaseDetails):
    pass


class CaseBranchIn(BaseBranch[CaseTrailIn], CaseBranchDetails):
    pass


class CaseBranchOut(BranchOut[CaseTrailOut, CaseDetails]):
    pass


class CaseFormDataIn(CaseTrailBase, BaseFormDataIn):
    targets: Targets = Field(default_factory=dict)


class CaseFormDataOut(CaseTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    targets: dict[TargetKind, Target]
