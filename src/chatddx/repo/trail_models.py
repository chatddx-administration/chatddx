# src/chatddx/repo/trail_models.py
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import (
    PROTECT,
    CharField,
    DecimalField,
    ForeignKey,
    IntegerField,
    JSONField,
    PositiveIntegerField,
    TextField,
    URLField,
)

from chatddx.core.choices import (
    CoercionChoices,
    ProviderChoices,
    ToolChoices,
    ValidationChoices,
)
from chatddx.core.decimals import DecimalDecoder, DecimalEncoder
from chatddx.core.django_fields import JSONSchemaField, RelatedArrayField
from chatddx.repo.base import TrailModel


class ConnectionTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_connection"

    provider = CharField(max_length=255, choices=ProviderChoices.choices)
    model = CharField(max_length=255)
    endpoint = URLField(max_length=2048)
    profile: JSONField[dict[str, Any]] = JSONField(
        default=dict,
        blank=True,
    )


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
    logit_bias: JSONField[dict[str, Decimal]] = JSONField(
        default=dict,
        blank=True,
        encoder=DecimalEncoder,
        decoder=DecimalDecoder,
    )
    provider_params: JSONField[dict[str, Any]] = JSONField(
        default=dict,
        blank=True,
    )
    stop_sequences: JSONField[list[str] | None] = JSONField(
        default=None,
        null=True,
        blank=True,
    )


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


class CaseTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_case"

    payload = TextField()


class ExpectTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_expect"

    payload = TextField()
    case = ForeignKey(
        CaseTrailModel,
        on_delete=PROTECT,
        related_name="expects",
    )
    output_type = ForeignKey(
        OutputTypeTrailModel,
        on_delete=PROTECT,
        related_name="expects",
    )


class ToolTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_tool"

    command = CharField(
        max_length=255,
        db_index=True,
        help_text="Name of the tool",
    )
    type = CharField(
        max_length=50,
        choices=ToolChoices.choices,
        default=ToolChoices.FUNCTION,
        help_text="The type of tool.",
    )
    description = TextField()
    parameters = JSONSchemaField()


class ToolGroupTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_tool_group"

    instructions = TextField()
    tools = RelatedArrayField(  # type: ignore
        IntegerField(),
        associated_model=ToolTrailModel,
        default=list,
    )


class AgentTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_agent"

    instructions = TextField()
    connection = ForeignKey(
        ConnectionTrailModel,
        on_delete=PROTECT,
    )
    sampling_params = ForeignKey(
        SamplingParamsTrailModel,
        on_delete=PROTECT,
    )
    output_type = ForeignKey(
        OutputTypeTrailModel,
        on_delete=PROTECT,
    )
    tool_group = ForeignKey(
        ToolGroupTrailModel,
        on_delete=PROTECT,
    )
