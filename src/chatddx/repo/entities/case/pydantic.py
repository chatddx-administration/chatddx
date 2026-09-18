from pydantic import Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.expect import ExpectTrailSchema
from chatddx.repo.entities.expect.pydantic import ExpectTrailSpec
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
    expects: list[ExpectTrailSchema] = Field(
        json_schema_extra={"exclude_from_fingerprint": True},
        default_factory=list,
    )


class CaseTrailSchemaRef(
    TrailSchemaRef,
    CaseTrailBase,
):
    pass


class CaseTrailSpec(CaseTrailBase, TrailSpec):
    expects: list[ExpectTrailSpec]


class CaseBranchSchema(BranchSchema[CaseTrailSchema]):
    pass


class CaseBranchSpec(BranchSpec[CaseTrailSpec]):
    pass


class CaseFormDataIn(CaseTrailBase, BaseFormDataIn):
    pass


class CaseFormDataOut(CaseTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
