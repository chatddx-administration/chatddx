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
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_configuration"

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
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_configuration_branch"

    target = ForeignKey(
        ConfigurationTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    instruction_branch = BranchRef("target__instruction", "instruction", Instruction)
    output_branch = BranchRef("target__output", "output", Output)
    coercion_branch = BranchRef("target__coercion", "coercion", Coercion)
    reasoning_branch = BranchRef("target__reasoning", "reasoning", Reasoning)
    sampling_branch = BranchRef("target__sampling", "sampling", Sampling)
    toolset_branch = BranchRef("target__toolset", "toolset", Toolset)


class Configuration(BranchProxy, ConfigurationBranchModel, Sharable):
    target: ConfigurationTrailModel

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Configuration"
        verbose_name_plural = "Configurations"


class SharedConfiguration(BranchProxy, ConfigurationBranchModel, Sharable):
    target: ConfigurationTrailModel

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Configuration"
        verbose_name_plural = "Shared Configurations"
