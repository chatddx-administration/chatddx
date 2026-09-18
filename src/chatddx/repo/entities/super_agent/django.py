# pyright: basic

from chatddx.django.orm.utils import Sharable
from chatddx.repo.entities.agent.django import AgentBranchModel, AgentTrailModel
from chatddx.repo.families.django import BranchProxy


class SuperAgent(BranchProxy, AgentBranchModel, Sharable):
    target: AgentTrailModel

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Agent"
        verbose_name_plural = "Agents"


class SharedSuperAgent(BranchProxy, AgentBranchModel, Sharable):
    target: AgentTrailModel

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Agent"
        verbose_name_plural = "Shared Agents"
