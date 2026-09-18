# pyright: basic

from django.db.models import (
    PROTECT,
    CharField,
    ForeignKey,
    TextField,
)

from chatddx.core.choices import ToolChoices
from chatddx.core.django_fields import JSONSchemaField
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ToolTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_tool"

    command = CharField(
        max_length=255,
        db_index=True,
        help_text="Command the tool invoces",
    )
    type = CharField(
        max_length=50,
        choices=ToolChoices.choices,
        default=ToolChoices.FUNCTION,
        help_text="The type of tool.",
    )
    description = TextField()
    parameters = JSONSchemaField()


class ToolBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_tool_branch"

    target = ForeignKey(
        ToolTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Tool(BranchProxy, ToolBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Tool"
        verbose_name_plural = "Tools"
