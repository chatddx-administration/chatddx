# pyright: basic

from django.db.models import PROTECT, CharField, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class CoercionTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_coercion"

    mode = CharField(max_length=16)
    schema_prompt = TextField(null=True, blank=True)


class CoercionBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_coercion_branch"

    target = ForeignKey(
        CoercionTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Coercion(BranchProxy, CoercionBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Coercion"
        verbose_name_plural = "Coercions"
