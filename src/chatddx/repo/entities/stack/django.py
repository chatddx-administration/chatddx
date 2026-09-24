# pyright: basic

from django.db.models import PROTECT, ForeignKey

from chatddx.repo.entities.llm.django import LLM, LLMTrailModel
from chatddx.repo.entities.machine.django import Machine, MachineTrailModel
from chatddx.repo.entities.os.django import Os, OsTrailModel
from chatddx.repo.entities.serving.django import Serving, ServingTrailModel
from chatddx.repo.families.branch_refs import BranchRef
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class StackTrailModel(TrailModel):
    machine_id: int
    os_id: int | None
    host_os_id: int | None
    llm_id: int
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
    llm = ForeignKey(
        LLMTrailModel,
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

    class Meta:
        db_table = "repo_stack_trail"


class StackBranchModel(BranchModel):
    trail = ForeignKey(
        StackTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    machine_branch = BranchRef("trail__machine", "machine", Machine)
    os_branch = BranchRef("trail__os", "os", Os)
    host_os_branch = BranchRef("trail__host_os", "os", Os)
    llm_branch = BranchRef("trail__llm", "llm", LLM)
    serving_branch = BranchRef("trail__serving", "serving", Serving)

    class Meta(BranchModel.Meta):
        db_table = "repo_stack_branch"


class Stack(BranchProxy, StackBranchModel):
    trail: StackTrailModel

    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Stack"
        verbose_name_plural = "Stacks"
