# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.django.orm.utils import Sharable
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class CaseTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_case"

    payload = TextField()


class CaseBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_case_branch"

    target = ForeignKey(
        CaseTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Case(BranchProxy, CaseBranchModel, Sharable):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Case"
        verbose_name_plural = "Cases"


class SharedCase(BranchProxy, CaseBranchModel, Sharable):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Case"
        verbose_name_plural = "Shared Cases"
