# pyright: basic

from django.db.models import PROTECT, ForeignKey

from chatddx.django.orm.annotations import BranchRef
from chatddx.django.orm.utils import Sharable
from chatddx.repo.entities.coercion.django import Coercion, CoercionTrailModel
from chatddx.repo.entities.instruction.django import Instruction, InstructionTrailModel
from chatddx.repo.entities.output.django import Output, OutputTrailModel
from chatddx.repo.entities.reasoning.django import Reasoning, ReasoningTrailModel
from chatddx.repo.entities.sampling.django import Sampling, SamplingTrailModel
from chatddx.repo.entities.toolset.django import Toolset, ToolsetTrailModel
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


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


class ConfigurationBranchModel(BranchModel):
    trail = ForeignKey(
        ConfigurationTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    instruction_branch = BranchRef("trail__instruction", "instruction", Instruction)
    output_branch = BranchRef("trail__output", "output", Output)
    coercion_branch = BranchRef("trail__coercion", "coercion", Coercion)
    reasoning_branch = BranchRef("trail__reasoning", "reasoning", Reasoning)
    sampling_branch = BranchRef("trail__sampling", "sampling", Sampling)
    toolset_branch = BranchRef("trail__toolset", "toolset", Toolset)


class Configuration(BranchProxy, ConfigurationBranchModel, Sharable):
    trail: ConfigurationTrailModel

    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Configuration"
        verbose_name_plural = "Configurations"


class SharedConfiguration(BranchProxy, ConfigurationBranchModel, Sharable):
    trail: ConfigurationTrailModel

    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Shared Configuration"
        verbose_name_plural = "Shared Configurations"
