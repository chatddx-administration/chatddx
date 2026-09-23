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
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_sampling"

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
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_sampling_branch"

    target = ForeignKey(
        SamplingTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Sampling(BranchProxy, SamplingBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Sampling"
        verbose_name_plural = "Sampling"
