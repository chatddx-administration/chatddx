# pyright: basic

from django.db.models import PROTECT, ForeignKey, IntegerField, TextField

from chatddx.core.django_fields import RelatedArrayField
from chatddx.repo.entities.tool.django import ToolTrailModel
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ToolsetTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_toolset"

    guidance = TextField(null=True, blank=True)
    # ordered, as the model is shown them
    tools = RelatedArrayField(  # pyright: ignore[reportCallIssue]
        IntegerField(),
        associated_model=ToolTrailModel,
        default=list,
    )


class ToolsetBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_toolset_branch"

    target = ForeignKey(
        ToolsetTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Toolset(BranchProxy, ToolsetBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Toolset"
        verbose_name_plural = "Toolsets"
