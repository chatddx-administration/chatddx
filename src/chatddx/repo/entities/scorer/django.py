# pyright: basic

from django.db.models import PROTECT, CharField, ForeignKey, JSONField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ScorerTrailModel(TrailModel):
    function = CharField(max_length=255)
    view = CharField(max_length=32)
    target_kind = CharField(max_length=32, null=True, blank=True)
    args = JSONField(default=dict, blank=True)

    class Meta:
        db_table = "repo_scorer_trail"


class ScorerBranchModel(BranchModel):
    trail = ForeignKey(
        ScorerTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_scorer_branch"


class Scorer(BranchProxy, ScorerBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
