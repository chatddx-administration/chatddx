from pydantic import Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.expect.pydantic import ExpectBranchSpec
from chatddx.repo.families import (
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchSchema,
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


class CaseBranchSchema(BranchSchema[CaseTrailSchema]):
    # `expects` comes from BranchSchemaDetails, as the branch names of the
    # expectations this version of the case carries.
    pass


class CaseBranchSpec(BranchSpec[CaseTrailSpec]):
    expects: list[ExpectBranchSpec] = Field(default_factory=list)


class CaseFormDataIn(CaseTrailBase, BaseFormDataIn):
    pass


class CaseFormDataOut(CaseTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
