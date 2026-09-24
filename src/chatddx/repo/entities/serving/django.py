# pyright: basic

from django.db.models import PROTECT, ForeignKey, JSONField, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ServingTrailModel(TrailModel):
    engine = TextField()
    # order-free: vLLM reads its arguments and environment as sets
    args = JSONField(default=dict, blank=True)
    env = JSONField(default=dict, blank=True)

    class Meta:
        db_table = "repo_serving_trail"


class ServingBranchModel(BranchModel):
    trail = ForeignKey(
        ServingTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_serving_branch"


class Serving(BranchProxy, ServingBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Serving"
        verbose_name_plural = "Servings"
