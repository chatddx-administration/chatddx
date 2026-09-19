from pydantic import Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.expect.pydantic import ExpectTrailSpec
from chatddx.repo.families import (
    RELATION,
    BaseBranch,
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchDetailsPatch,
    BranchSchemaDetails,
    BranchSpec,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)


class CaseTrailBase(BaseTrail):
    payload: str


class CaseTrailSchema(CaseTrailBase, TrailSchema):
    pass


class CaseTrailSchemaRef(
    TrailSchemaRef,
    CaseTrailBase,
):
    pass


class CaseTrailSpec(CaseTrailBase, TrailSpec):
    pass


class CaseBranchDetails(BranchSchemaDetails):
    # Which expectations a case carries is the owner's, not the payload's, so
    # it belongs to the branch. The names are expect *branch* names: two cases
    # that expect the same thing share one content-addressed trail, so a trail
    # cannot say whose expectation it is.
    expects: list[str] | None = Field(
        default=None,
        json_schema_extra={RELATION: "expect"},
    )


class CaseBranchDetailsPatch(BranchDetailsPatch):
    expects: list[str] | None = None


class CaseBranchSchema(BaseBranch[CaseTrailSchema], CaseBranchDetails):
    pass


class CaseBranchSpec(BranchSpec[CaseTrailSpec]):
    expects: list[ExpectTrailSpec] = Field(default_factory=list)


class CaseFormDataIn(CaseTrailBase, BaseFormDataIn):
    pass


class CaseFormDataOut(CaseTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
