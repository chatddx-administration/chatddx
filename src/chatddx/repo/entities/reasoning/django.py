# pyright: basic

from django.db.models import PROTECT, CharField, ForeignKey, PositiveIntegerField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ReasoningTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_reasoning"

    effort = CharField(max_length=16)
    budget = PositiveIntegerField(null=True, blank=True)


class ReasoningBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_reasoning_branch"

    target = ForeignKey(
        ReasoningTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Reasoning(BranchProxy, ReasoningBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Reasoning"
        verbose_name_plural = "Reasoning"
