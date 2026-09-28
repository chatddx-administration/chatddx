# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, TrailModel


class OsTrailModel(TrailModel):
    toplevel = TextField()

    class Meta(TrailModel.Meta):
        db_table = "repo_os_trail"


class OsBranchModel(BranchModel):
    trail = ForeignKey(
        OsTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_os_branch"
