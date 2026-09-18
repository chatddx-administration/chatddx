# pyright: basic

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import (
    PROTECT,
    DecimalField,
    ForeignKey,
    IntegerField,
    JSONField,
    PositiveIntegerField,
)

from chatddx.core.decimals import DecimalDecoder, DecimalEncoder
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class SamplingParamsTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_sampling_params"

    temperature = DecimalField(
        default=None,
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=3,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(2),
        ],
    )
    top_p = DecimalField(
        default=None,
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=3,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ],
    )
    top_k = IntegerField(
        default=None,
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    max_tokens = PositiveIntegerField(
        default=None,
        null=True,
        blank=True,
    )
    seed = IntegerField(
        default=None,
        null=True,
        blank=True,
    )
    n = PositiveIntegerField(
        default=None,
        null=True,
        blank=True,
    )
    presence_penalty = DecimalField(
        default=None,
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=3,
    )
    frequency_penalty = DecimalField(
        default=None,
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=3,
    )
    logit_bias = JSONField(
        default=dict,
        blank=True,
        encoder=DecimalEncoder,
        decoder=DecimalDecoder,
    )
    provider_params = JSONField(
        default=dict,
        blank=True,
    )
    stop_sequences = JSONField(
        default=None,
        null=True,
        blank=True,
    )


class SamplingParamsBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_sampling_params_branch"

    target = ForeignKey(
        SamplingParamsTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class SamplingParams(BranchProxy, SamplingParamsBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Sampling parameters"
        verbose_name_plural = "Sampling parameters"
