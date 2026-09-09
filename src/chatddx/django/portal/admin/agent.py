# pyright: basic
from django.contrib import admin
from django.http import HttpRequest

from chatddx.django.portal.admin.base import BranchModelAdmin
from chatddx.django.portal.forms import AgentForm
from chatddx.repo import proxies


@admin.register(proxies.Agent)
class AgentAdmin(BranchModelAdmin[proxies.Agent]):
    form = AgentForm
    name = "agent"
    list_display = list(BranchModelAdmin.list_display) + ["collaborators_csv"]

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)

        return qs.filter(
            owner__name=request.user.username,
        )


@admin.register(proxies.SharedAgent)
class SharedAgentAdmin(AgentAdmin):
    list_display = list(AgentAdmin.list_display) + ["owner"]

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)

        return qs.filter(
            collaborators__name=request.user.username,
        )
