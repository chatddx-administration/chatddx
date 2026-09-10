# src/chatddx/repo/proxies.py
# pyright: basic
from functools import cached_property

import tomli_w
from django.contrib import admin
from django.db.models import Manager

from chatddx.core.models import IdentityModel
from chatddx.repo.base import BranchProxy
from chatddx.repo.branch_models import (
    AgentBranchModel,
    CaseBranchModel,
    ConnectionBranchModel,
    OutputTypeBranchModel,
    SamplingParamsBranchModel,
    ToolBranchModel,
    ToolGroupBranchModel,
)
from chatddx.repo.trail_models import AgentTrailModel, ConnectionTrailModel


class Shared:
    collaborators: Manager[IdentityModel]

    @admin.display(description="Collaborators")
    def collaborators_csv(self):
        return ", ".join([str(c) for c in self.collaborators.all()]) or None


class SuperAgent(BranchProxy, AgentBranchModel, Shared):
    target: AgentTrailModel

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Agent"
        verbose_name_plural = "Agents"


class SharedSuperAgent(BranchProxy, AgentBranchModel, Shared):
    target: AgentTrailModel

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Agent"
        verbose_name_plural = "Shared Agents"


class Agent(BranchProxy, AgentBranchModel, Shared):
    target: AgentTrailModel

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Agent (simple)"
        verbose_name_plural = "Agents (simple)"


class SharedAgent(BranchProxy, AgentBranchModel, Shared):
    target: AgentTrailModel

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Agent (simple)"
        verbose_name_plural = "Shared Agents (simple)"


class Connection(BranchProxy, ConnectionBranchModel):
    target: ConnectionTrailModel

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Connection"
        verbose_name_plural = "Connections"

    @cached_property
    def profile_toml(self) -> str:
        return tomli_w.dumps(self.target.profile)


class OutputType(BranchProxy, OutputTypeBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Output type"
        verbose_name_plural = "Output types"


class SamplingParams(BranchProxy, SamplingParamsBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Sampling parameters"
        verbose_name_plural = "Sampling parameters"


class ToolGroup(BranchProxy, ToolGroupBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Tool group"
        verbose_name_plural = "Tool groups"


class Tool(BranchProxy, ToolBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Tool"
        verbose_name_plural = "Tools"


class Case(BranchProxy, CaseBranchModel, Shared):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Case"
        verbose_name_plural = "Cases"


class SharedCase(BranchProxy, CaseBranchModel, Shared):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Case"
        verbose_name_plural = "Shared Cases"
