# pyright: basic

from django.db.models import PROTECT, CharField, ForeignKey, TextField

from chatddx.repo.families.django import (
    BranchModel,
    BranchProxy,
    OrderedJSONField,
    TrailModel,
)


class ToolTrailModel(TrailModel):
    name = CharField(max_length=64)
    description = TextField(blank=True)
    parameters = OrderedJSONField()


class ToolBranchModel(BranchModel):
    target = ForeignKey(
        ToolTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Tool(BranchProxy, ToolBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Tool"
        verbose_name_plural = "Tools"
