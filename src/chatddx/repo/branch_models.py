# src/chatddx/django/repo/models/history.py
from __future__ import annotations

from django.db.models import PROTECT, ForeignKey, ManyToManyField

from chatddx.core.models import TagModel
from chatddx.repo.base import BranchModel
from chatddx.repo.trail_models import (
    AgentTrailModel,
    CaseTrailModel,
    ConnectionTrailModel,
    ExpectTrailModel,
    OutputTypeTrailModel,
    SamplingParamsTrailModel,
    ToolGroupTrailModel,
    ToolTrailModel,
)

BranchModelRegistry = dict[str, dict[int, BranchModel]]


class AgentBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_agent_branch"

    target = ForeignKey(
        AgentTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class ConnectionBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_connection_branch"

    target = ForeignKey(
        ConnectionTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class SamplingParamsBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_sampling_params_branch"

    target = ForeignKey(
        SamplingParamsTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class ToolGroupBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_tool_group_branch"

    target = ForeignKey(
        ToolGroupTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class ToolBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_tool_branch"

    target = ForeignKey(
        ToolTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class CaseBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_case_branch"

    target = ForeignKey(
        CaseTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    # Tags are plain labels, not repo-matter: no trail/branch pair backs
    # them and there is no central place they're managed. They just let a
    # case branch be found by one or more short labels.
    tags = ManyToManyField(
        TagModel,
        blank=True,
        related_name="case_branches",
    )


class OutputTypeBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_output_type_branch"

    target = ForeignKey(
        OutputTypeTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class ExpectBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_expect_branch"

    target = ForeignKey(
        ExpectTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )
