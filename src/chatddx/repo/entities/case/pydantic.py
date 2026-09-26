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

type TargetKind = Literal["diagnosis", "warning", "disposition", "dont_miss"]
TARGET_KINDS: tuple[TargetKind, ...] = get_args(TargetKind.__value__)

EXPECTS_NONE: frozenset[TargetKind] = frozenset({"warning"})

type Language = Literal["en", "sv"]

type Words = Annotated[str, StringConstraints(min_length=1)]


class Expected(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    text: Words | None = None
    pattern: Words | None = None

    @model_validator(mode="after")
    def _says_something(self) -> "Expected":
        if self.text is None and self.pattern is None:
            raise ValueError("a target gives its text, its pattern, or both")

        return self


type Target = Expected | Literal[False]


def pattern_of(target: object) -> str | None:
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
    # the case taken out of sight, its timeline kept: what lists cases, plans
    # with them or looks them up passes it by, and the runs it held keep
    # their name and targets by it where no other case holds their vignette
    deleted: bool = False


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
