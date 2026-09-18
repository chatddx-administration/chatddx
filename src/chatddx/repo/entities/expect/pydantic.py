from typing import override

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.scorer.pydantic import (
    ScorerFormDataIn,
    ScorerTrailSchema,
    ScorerTrailSpec,
)
from chatddx.repo.families import (
    BranchSchema,
    BranchSpec,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)
from chatddx.repo.families.pydantic import BaseFormDataIn, BaseFormDataOut, BaseTrail


class ExpectTrailBase(BaseTrail):
    payload: str


class ExpectTrailSchema(ExpectTrailBase, TrailSchema):
    scorer: ScorerTrailSchema


class ExpectTrailSchemaRef(
    TrailSchemaRef,
    ExpectTrailBase,
):
    scorer_id: int


class ExpectTrailSpec(ExpectTrailBase, TrailSpec):
    scorer: ScorerTrailSpec


class ExpectBranchSchema(BranchSchema[ExpectTrailSchema]):
    pass


class ExpectBranchSpec(BranchSpec[ExpectTrailSpec]):
    pass


class ExpectFormDataIn(ExpectTrailBase, BaseFormDataIn):
    scorer: ScorerFormDataIn


class ExpectFormDataOut(ExpectTrailBase, BaseFormDataOut):
    scorer: CoercedStr
