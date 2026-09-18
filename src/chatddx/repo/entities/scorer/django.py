# pyright: basic

from django.db.models import (
    PROTECT,
    CharField,
    ForeignKey,
)

from chatddx.django.orm.utils import Sharable
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ScorerTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_scorer"

    command = CharField(max_length=255)


class ScorerBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_scorer_branch"

    target = ForeignKey(
        ScorerTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Scorer(BranchProxy, ScorerBranchModel, Sharable):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Scorer"
        verbose_name_plural = "Scorers"


class SharedScorer(BranchProxy, ScorerBranchModel, Sharable):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Scorer"
        verbose_name_plural = "Shared Scorers"
