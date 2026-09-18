# pyright: basic

from django.db.models import (
    PROTECT,
    CharField,
    ForeignKey,
    IntegerField,
)

from chatddx.core.choices import CoercionChoices, ValidationChoices
from chatddx.core.django_fields import JSONSchemaField
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class OutputTypeTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_output_type"

    definition = JSONSchemaField(
        default=dict,
    )
    output_retries = IntegerField(default=1)
    validation_strategy = CharField(
        max_length=255,
        default=ValidationChoices.INFORM,
        choices=ValidationChoices.choices,
    )
    coercion_strategy = CharField(
        max_length=255,
        default=CoercionChoices.NATIVE,
        choices=CoercionChoices.choices,
    )


class OutputTypeBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_output_type_branch"

    target = ForeignKey(
        OutputTypeTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class OutputType(BranchProxy, OutputTypeBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Output type"
        verbose_name_plural = "Output types"
