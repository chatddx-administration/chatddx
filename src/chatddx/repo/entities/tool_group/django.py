# pyright: basic

from django.db.models import (
    PROTECT,
    ForeignKey,
    IntegerField,
    TextField,
)

from chatddx.core.django_fields import RelatedArrayField
from chatddx.repo.entities.tool.django import ToolTrailModel
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ToolGroupTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_tool_group"

    instructions = TextField()
    tools = RelatedArrayField(  # pyright: ignore[reportCallIssue]
        IntegerField(),
        associated_model=ToolTrailModel,
        default=list,
    )


class ToolGroupBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_tool_group_branch"

    target = ForeignKey(
        ToolGroupTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class ToolGroup(BranchProxy, ToolGroupBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Tool group"
        verbose_name_plural = "Tool groups"
