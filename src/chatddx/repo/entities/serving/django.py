# pyright: basic

from django.db.models import PROTECT, ForeignKey, JSONField, TextField

from chatddx.repo.families.django import BranchModel, TrailModel


class ServingTrailModel(TrailModel):
    engine = TextField()
    args = JSONField(default=dict, blank=True)
    env = JSONField(default=dict, blank=True)

    class Meta(TrailModel.Meta):
        db_table = "repo_serving_trail"


class ServingBranchModel(BranchModel):
    trail = ForeignKey(
        ServingTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_serving_branch"
