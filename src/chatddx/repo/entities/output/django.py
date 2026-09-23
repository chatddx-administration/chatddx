# pyright: basic

from django.db.models import PROTECT, ForeignKey, JSONField, TextField

from chatddx.repo.families.django import (
    BranchModel,
    BranchProxy,
    OrderedJSONField,
    TrailModel,
)


class OutputTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_output"

    # null for free text
    schema = OrderedJSONField(null=True, blank=True)
    guidance = TextField(null=True, blank=True)
    views = JSONField(default=dict, blank=True)


class OutputBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_output_branch"

    target = ForeignKey(
        OutputTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Output(BranchProxy, OutputBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Output"
        verbose_name_plural = "Outputs"
