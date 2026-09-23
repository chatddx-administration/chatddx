# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class OsTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_os"

    toplevel = TextField()


class OsBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_os_branch"

    target = ForeignKey(
        OsTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Os(BranchProxy, OsBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "OS"
        verbose_name_plural = "OSes"
