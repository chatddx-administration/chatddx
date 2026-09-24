# pyright: basic

from django.db.models import PROTECT, CharField, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class CoercionTrailModel(TrailModel):
    mode = CharField(max_length=16)
    schema_prompt = TextField(null=True, blank=True)
    tool_description = TextField(null=True, blank=True)

    class Meta:
        db_table = "repo_coercion_trail"


class CoercionBranchModel(BranchModel):
    trail = ForeignKey(
        CoercionTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_coercion_branch"


class Coercion(BranchProxy, CoercionBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Coercion"
        verbose_name_plural = "Coercions"
