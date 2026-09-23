# pyright: basic

from django.db.models import PROTECT, ForeignKey, JSONField, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ServingTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_serving"

    engine = TextField()
    # order-free: vLLM reads its arguments and environment as sets
    args = JSONField(default=dict, blank=True)
    env = JSONField(default=dict, blank=True)


class ServingBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_serving_branch"

    target = ForeignKey(
        ServingTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Serving(BranchProxy, ServingBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Serving"
        verbose_name_plural = "Servings"
