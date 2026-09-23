# pyright: basic

from django.db.models import (
    PROTECT,
    CharField,
    FloatField,
    ForeignKey,
    IntegerField,
    JSONField,
    PositiveIntegerField,
)

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class SamplingTrailModel(TrailModel):
    defaults = CharField(max_length=16)

    # doubles, like the numbers a request carries
    temperature = FloatField(null=True, blank=True)
    top_p = FloatField(null=True, blank=True)
    top_k = IntegerField(null=True, blank=True)
    max_tokens = PositiveIntegerField(null=True, blank=True)
    presence_penalty = FloatField(null=True, blank=True)
    frequency_penalty = FloatField(null=True, blank=True)
    stop = JSONField(null=True, blank=True)


class SamplingBranchModel(BranchModel):
    target = ForeignKey(
        SamplingTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Sampling(BranchProxy, SamplingBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Sampling"
        verbose_name_plural = "Sampling"
