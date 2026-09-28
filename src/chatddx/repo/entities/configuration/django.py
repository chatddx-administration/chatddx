# pyright: basic

from django.db.models import PROTECT, ForeignKey

from chatddx.repo.entities.coercion.django import CoercionTrailModel
from chatddx.repo.entities.instruction.django import InstructionTrailModel
from chatddx.repo.entities.output.django import OutputTrailModel
from chatddx.repo.entities.reasoning.django import ReasoningTrailModel
from chatddx.repo.entities.sampling.django import SamplingTrailModel
from chatddx.repo.entities.toolset.django import ToolsetTrailModel
from chatddx.repo.families.django import (
    BranchModel,
    TrailModel,
)


class ConfigurationTrailModel(TrailModel):
    instruction_id: int
    output_id: int
    coercion_id: int
    reasoning_id: int
    sampling_id: int
    toolset_id: int | None

    instruction = ForeignKey(
        InstructionTrailModel,
        on_delete=PROTECT,
        related_name="configurations",
    )
    output = ForeignKey(
        OutputTrailModel,
        on_delete=PROTECT,
        related_name="configurations",
    )
    coercion = ForeignKey(
        CoercionTrailModel,
        on_delete=PROTECT,
        related_name="configurations",
    )
    reasoning = ForeignKey(
        ReasoningTrailModel,
        on_delete=PROTECT,
        related_name="configurations",
    )
    sampling = ForeignKey(
        SamplingTrailModel,
        on_delete=PROTECT,
        related_name="configurations",
    )
    toolset = ForeignKey(
        ToolsetTrailModel,
        on_delete=PROTECT,
        null=True,
        blank=True,
        related_name="configurations",
    )

    class Meta(TrailModel.Meta):
        db_table = "repo_configuration_trail"


class ConfigurationBranchModel(BranchModel):
    trail = ForeignKey(
        ConfigurationTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_configuration_branch"
