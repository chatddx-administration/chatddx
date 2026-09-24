# pyright: basic

from django.db.models import PROTECT, ForeignKey, JSONField, TextField

from chatddx.repo.families.django import (
    BranchModel,
    BranchProxy,
    OrderedJSONField,
    TrailModel,
)


class OutputTrailModel(TrailModel):
    # null for free text
    json_schema = OrderedJSONField(null=True, blank=True)
    guidance = TextField(null=True, blank=True)
    views = JSONField(default=dict, blank=True)


class OutputBranchModel(BranchModel):
    trail = ForeignKey(
        OutputTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Output(BranchProxy, OutputBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Output"
        verbose_name_plural = "Outputs"
