# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


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


class LLM(BranchProxy, LLMBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
