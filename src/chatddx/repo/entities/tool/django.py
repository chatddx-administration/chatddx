# pyright: basic

from django.db.models import PROTECT, CharField, ForeignKey, TextField

from chatddx.repo.families.django import (
    BranchModel,
    BranchProxy,
    OrderedJSONField,
    TrailModel,
)


class ToolTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_tool"

    name = CharField(max_length=64)
    description = TextField(blank=True)
    parameters = OrderedJSONField()


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
