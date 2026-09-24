# pyright: basic

from django.db.models import PROTECT, ForeignKey, IntegerField, TextField

from chatddx.core.django_fields import RelatedArrayField
from chatddx.repo.entities.tool.django import ToolTrailModel
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ToolsetTrailModel(TrailModel):
    guidance = TextField(null=True, blank=True)
    # ordered, as the LLM is shown them
    tools = RelatedArrayField(  # pyright: ignore[reportCallIssue]
        IntegerField(),
        associated_model=ToolTrailModel,
        default=list,
    )


class ToolsetBranchModel(BranchModel):
    trail = ForeignKey(
        ToolsetTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Toolset(BranchProxy, ToolsetBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Toolset"
        verbose_name_plural = "Toolsets"
