# pyright: basic

from django.contrib import admin

from chatddx.django.portal.branch import BranchModelAdmin
from chatddx.django.portal.forms.agent import AgentForm
from chatddx.django.portal.mixins import SharedMixin
from chatddx.repo.entities.agent.django import Agent, SharedAgent


@admin.register(Agent)
class AgentAdmin(BranchModelAdmin[Agent]):
    form = AgentForm
    name = "agent"
    list_display = list(BranchModelAdmin.list_display) + ["collaborators_csv"]


@admin.register(SharedAgent)
class SharedAgentAdmin(SharedMixin, AgentAdmin):
    list_display = list(AgentAdmin.list_display) + ["owner"]
