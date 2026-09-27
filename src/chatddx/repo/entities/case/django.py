# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.repo.families.django import (
    BranchModel,
    TrailModel,
)


class CaseTrailModel(TrailModel):
    vignette = TextField()

    class Meta(TrailModel.Meta):
        db_table = "repo_case_trail"


class CaseBranchModel(BranchModel):
    trail = ForeignKey(
        CaseTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_case_branch"
