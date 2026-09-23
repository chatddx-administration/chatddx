# pyright: basic

from django.db.models import PROTECT, ForeignKey

from chatddx.django.orm.annotations import BranchRef
from chatddx.repo.entities.machine.django import Machine, MachineTrailModel
from chatddx.repo.entities.model.django import LanguageModel, ModelTrailModel
from chatddx.repo.entities.os.django import Os, OsTrailModel
from chatddx.repo.entities.serving.django import Serving, ServingTrailModel
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class StackTrailModel(TrailModel):
    machine_id: int
    os_id: int | None
    host_os_id: int | None
    model_id: int
    serving_id: int | None

    machine = ForeignKey(
        MachineTrailModel,
        on_delete=PROTECT,
        related_name="stacks",
    )
    os = ForeignKey(
        OsTrailModel,
        on_delete=PROTECT,
        null=True,
        blank=True,
        related_name="stacks",
    )
    host_os = ForeignKey(
        OsTrailModel,
        on_delete=PROTECT,
        null=True,
        blank=True,
        related_name="hosted_stacks",
    )
    model = ForeignKey(
        ModelTrailModel,
        on_delete=PROTECT,
        related_name="stacks",
    )
    serving = ForeignKey(
        ServingTrailModel,
        on_delete=PROTECT,
        null=True,
        blank=True,
        related_name="stacks",
    )


class StackBranchModel(BranchModel):
    target = ForeignKey(
        StackTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    machine_branch = BranchRef("target__machine", "machine", Machine)
    os_branch = BranchRef("target__os", "os", Os)
    host_os_branch = BranchRef("target__host_os", "os", Os)
    model_branch = BranchRef("target__model", "model", LanguageModel)
    serving_branch = BranchRef("target__serving", "serving", Serving)


class Stack(BranchProxy, StackBranchModel):
    target: StackTrailModel

    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Stack"
        verbose_name_plural = "Stacks"
