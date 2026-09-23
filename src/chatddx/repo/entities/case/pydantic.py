"""
A case: its payload, as the model receives it through the instruction's
`case` variable.

What a case is expected to yield is not the registry's any more: targets are
inspect's, keyed by the case, and a batch's scorers read them
(new-datamodel.md §7).
"""

from pydantic import Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.families import (
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchSchema,
    BranchSpec,
    Details,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)


class CaseTrailBase(BaseTrail):
    payload: str


class CaseTrailSchema(CaseTrailBase, TrailSchema):
    pass


class CaseTrailSchemaRef(TrailSchemaRef, CaseTrailBase):
    pass


class CaseTrailSpec(CaseTrailBase, TrailSpec):
    pass


class CaseBranchSchema(BranchSchema[CaseTrailSchema]):
    pass


class CaseBranchSpec(BranchSpec[CaseTrailSpec, Details]):
    pass


class CaseFormDataIn(CaseTrailBase, BaseFormDataIn):
    pass


class CaseFormDataOut(CaseTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
