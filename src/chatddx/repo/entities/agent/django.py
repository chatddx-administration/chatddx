# pyright: basic

from django.db.models import (
    PROTECT,
    ForeignKey,
)

from chatddx.django.orm.utils import Sharable
from chatddx.repo.entities.connection.django import ConnectionTrailModel
from chatddx.repo.entities.instruction.django import InstructionTrailModel
from chatddx.repo.entities.output_type.django import OutputTypeTrailModel
from chatddx.repo.entities.sampling_params.django import SamplingParamsTrailModel
from chatddx.repo.entities.tool_group.django import ToolGroupTrailModel
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class AgentTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_agent"

    instruction = ForeignKey(
        InstructionTrailModel,
        on_delete=PROTECT,
    )
    connection = ForeignKey(
        ConnectionTrailModel,
        on_delete=PROTECT,
    )
    sampling_params = ForeignKey(
        SamplingParamsTrailModel,
        on_delete=PROTECT,
    )
    output_type = ForeignKey(
        OutputTypeTrailModel,
        on_delete=PROTECT,
    )
    tool_group = ForeignKey(
        ToolGroupTrailModel,
        on_delete=PROTECT,
    )


class AgentBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_agent_branch"

    target = ForeignKey(
        AgentTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Agent(BranchProxy, AgentBranchModel, Sharable):
    target: AgentTrailModel

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Agent (simple)"
        verbose_name_plural = "Agents (simple)"


class SharedAgent(BranchProxy, AgentBranchModel, Sharable):
    target: AgentTrailModel

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Agent (simple)"
        verbose_name_plural = "Shared Agents (simple)"
