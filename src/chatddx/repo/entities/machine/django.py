# pyright: basic

from django.db.models import PROTECT, ForeignKey, UUIDField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class MachineTrailModel(TrailModel):
    machine_id = UUIDField()


class MachineBranchModel(BranchModel):
    target = ForeignKey(
        MachineTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Machine(BranchProxy, MachineBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Machine"
        verbose_name_plural = "Machines"
