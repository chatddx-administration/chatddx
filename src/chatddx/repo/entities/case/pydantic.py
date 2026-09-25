"""
A case: its vignette, as the LLM receives it through the instruction's
`case` variable, and what it is expected to yield.

The targets are details, not content: they change nothing the LLM reads,
and the vignette is what the case's fingerprint names. Like an LLM's facts,
they are versioned with the branch, and each score records the row whose
targets it read. inspect keeps a sample's target with the sample, and a case
is chatddx's sample. Unlike inspect's one target per sample, a case has one
per kind, and each scorer reads the kind it names.

A target is what is expected in plain words, its `text`, and the pattern the
pattern scorers find it by, its `pattern`. Either may be missing: the data
is taken as intended, and what is missing is shown as missing.

Its language is a detail too: the language its vignette is written in, and
one day everything a run sends with it.
"""

from typing import Annotated, Any, ClassVar, Literal, cast, get_args

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

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
type TargetKind = Literal["diagnosis", "warning", "disposition", "dont_miss"]
TARGET_KINDS: tuple[TargetKind, ...] = get_args(TargetKind.__value__)

# The kinds a case may expect none of: a plan that rightly raises no warning.
# `false` says so.
EXPECTS_NONE: frozenset[TargetKind] = frozenset({"warning"})

# the languages a case can be written in
type Language = Literal["en", "sv"]

type Words = Annotated[str, StringConstraints(min_length=1)]


class Expected(BaseModel):
    """What a case expects of one kind: its plain words, and its pattern."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    text: Words | None = None
    pattern: Words | None = None

    @model_validator(mode="after")
    def _says_something(self) -> "Expected":
        if self.text is None and self.pattern is None:
            raise ValueError("a target gives its text, its pattern, or both")

        return self


# what the case expects of a kind, or false where it expects none
type Target = Expected | Literal[False]


def pattern_of(target: object) -> str | None:
    """The pattern of a target as details keep it, or None where it has none."""
    if not isinstance(target, dict):
        return None

    pattern = cast(dict[str, Any], target).get("pattern")
    return pattern if isinstance(pattern, str) else None


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
    language: Language | None = None
    targets: Targets = Field(default_factory=dict)


class CaseTrailBase(BaseTrail):
    vignette: str


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
    language: Language | None = None
    targets: Targets = Field(default_factory=dict)


class CaseFormDataOut(CaseTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    language: Language | None
    targets: dict[TargetKind, Target]
