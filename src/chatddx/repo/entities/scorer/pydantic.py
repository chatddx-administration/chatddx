from pydantic import BaseModel

from chatddx.repo.families import (
    BranchSchema,
    BranchSpec,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)
from chatddx.repo.families.pydantic import BaseFormDataIn, BaseFormDataOut, BaseTrail


class ScorerBasePrimitives(BaseModel):
    command: str


class ScorerTrailBase(ScorerBasePrimitives, BaseTrail):
    pass


class ScorerTrailSchema(ScorerTrailBase, TrailSchema):
    pass


class ScorerTrailSchemaRef(
    TrailSchemaRef,
    ScorerTrailBase,
):
    pass


class ScorerTrailSpec(ScorerTrailBase, TrailSpec):
    pass


class ScorerBranchSchema(BranchSchema[ScorerTrailSchema]):
    pass


class ScorerBranchSpec(BranchSpec[ScorerTrailSpec]):
    pass


class ScorerFormDataIn(ScorerTrailBase, BaseFormDataIn):
    pass


class ScorerFormDataOut(ScorerTrailBase, BaseFormDataOut):
    pass
