# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class LLMTrailModel(TrailModel):
    snapshot = TextField()


class LLMBranchModel(BranchModel):
    trail = ForeignKey(
        LLMTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class LLM(BranchProxy, LLMBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
