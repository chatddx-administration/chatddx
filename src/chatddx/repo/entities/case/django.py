# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.django.orm.utils import Sharable
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class CaseTrailModel(TrailModel):
    vignette = TextField()


class CaseBranchModel(BranchModel):
    trail = ForeignKey(
        CaseTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Case(BranchProxy, CaseBranchModel, Sharable):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Case"
        verbose_name_plural = "Cases"


class SharedCase(BranchProxy, CaseBranchModel, Sharable):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Shared Case"
        verbose_name_plural = "Shared Cases"
