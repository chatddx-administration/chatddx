# pyright: basic

from django.db.models import (
    PROTECT,
    ForeignKey,
    TextField,
)

from chatddx.django.orm.utils import Sharable
from chatddx.repo.entities.scorer.django import ScorerTrailModel
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ExpectTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_expect"

    payload = TextField()
    scorer = ForeignKey(
        ScorerTrailModel,
        on_delete=PROTECT,
        related_name="expects",
    )


class ExpectBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_expect_branch"

    target = ForeignKey[ExpectTrailModel](
        ExpectTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Expect(BranchProxy, ExpectBranchModel, Sharable):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Expect"
        verbose_name_plural = "Expects"
