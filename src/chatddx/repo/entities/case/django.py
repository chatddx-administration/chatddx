# pyright: basic

from django.db.models import (
    CASCADE,
    PROTECT,
    ForeignKey,
    ManyToManyField,
    Model,
    TextField,
)

from chatddx.django.orm.utils import Sharable
from chatddx.repo.entities.expect.django import ExpectTrailModel
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class CaseTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_case"

    payload = TextField()

    expects = ManyToManyField(
        ExpectTrailModel,
        through="CaseExpect",
        through_fields=("case", "expect"),
        related_name="cases",
    )


class CaseExpect(Model):
    class Meta:
        app_label = "orm"
        db_table = "agents_case_expect_link"

    case = ForeignKey(CaseTrailModel, on_delete=CASCADE)
    expect = ForeignKey(ExpectTrailModel, on_delete=CASCADE)


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
