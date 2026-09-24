# pyright: basic

from django.db.models import PROTECT, CharField, ForeignKey, PositiveIntegerField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ReasoningTrailModel(TrailModel):
    effort = CharField(max_length=16)
    budget = PositiveIntegerField(null=True, blank=True)


class ReasoningBranchModel(BranchModel):
    trail = ForeignKey(
        ReasoningTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Reasoning(BranchProxy, ReasoningBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Reasoning"
        verbose_name_plural = "Reasoning"
