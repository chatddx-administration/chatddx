# pyright: basic

from django.db.models import PROTECT, ForeignKey, UUIDField

from chatddx.repo.families.django import BranchModel, TrailModel


class MachineTrailModel(TrailModel):
    machine_id = UUIDField()

    class Meta(TrailModel.Meta):
        db_table = "repo_machine_trail"


class MachineBranchModel(BranchModel):
    trail = ForeignKey(
        MachineTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_machine_branch"
