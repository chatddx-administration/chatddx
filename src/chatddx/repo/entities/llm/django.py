# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, TrailModel


class LLMTrailModel(TrailModel):
    snapshot = TextField()

    class Meta(TrailModel.Meta):
        db_table = "repo_llm_trail"


class LLMBranchModel(BranchModel):
    trail = ForeignKey(
        LLMTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_llm_branch"
