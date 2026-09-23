# pyright: basic

from django.db.models import PROTECT, CharField, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class CoercionTrailModel(TrailModel):
    mode = CharField(max_length=16)
    schema_prompt = TextField(null=True, blank=True)


class CoercionBranchModel(BranchModel):
    target = ForeignKey(
        CoercionTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Coercion(BranchProxy, CoercionBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Coercion"
        verbose_name_plural = "Coercions"
