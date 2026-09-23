# pyright: basic

from django.db.models import PROTECT, ForeignKey, UUIDField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class MachineTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_machine"

    machine_id = UUIDField()


class MachineBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_machine_branch"

    target = ForeignKey(
        MachineTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Machine(BranchProxy, MachineBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Machine"
        verbose_name_plural = "Machines"
