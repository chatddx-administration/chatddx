# pyright: basic

from django.db.models import PROTECT, ForeignKey

from chatddx.repo.entities.llm.django import LLMTrailModel
from chatddx.repo.entities.machine.django import MachineTrailModel
from chatddx.repo.entities.os.django import OsTrailModel
from chatddx.repo.entities.serving.django import ServingTrailModel
from chatddx.repo.families.django import BranchModel, TrailModel


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

    class Meta(TrailModel.Meta):
        db_table = "repo_stack_trail"


class StackBranchModel(BranchModel):
    trail = ForeignKey(
        StackTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_stack_branch"
