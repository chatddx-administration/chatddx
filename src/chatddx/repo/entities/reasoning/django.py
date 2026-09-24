# pyright: basic

from django.db.models import PROTECT, CharField, ForeignKey, PositiveIntegerField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ReasoningTrailModel(TrailModel):
    effort = CharField(max_length=16)
    budget = PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "repo_reasoning_trail"


class ReasoningBranchModel(BranchModel):
    trail = ForeignKey(
        ReasoningTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_reasoning_branch"


class Reasoning(BranchProxy, ReasoningBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Reasoning"
        verbose_name_plural = "Reasoning"
