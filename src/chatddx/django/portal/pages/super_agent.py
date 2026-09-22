# pyright: basic

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from chatddx.django.orm.qs import qs_super_agent
from chatddx.django.portal.branch import BranchModelAdmin
from chatddx.django.portal.forms.super_agent import SuperAgentForm
from chatddx.django.portal.typing import TypedModelAdmin
from chatddx.django.portal.utils import truncate_for_list_display
from chatddx.repo.entities.super_agent.django import SharedSuperAgent, SuperAgent
from chatddx.repo.todo import agent_relations


@admin.register(SuperAgent)
class SuperAgentAdmin(BranchModelAdmin[SuperAgent]):
    form = SuperAgentForm
    name = "agent"
    list_display = list(BranchModelAdmin.list_display) + [
        "instructions",
        "connection",
        "output_type",
        "sampling_params",
        "tool_group",
        "collaborators_csv",
    ]

    @admin.display(
        description="Instructions",
        ordering="target__instruction__definition",
    )
    def instructions(self, obj: SuperAgent) -> str:
        return truncate_for_list_display(obj.target.instruction.definition)

    @admin.display(description="Connection", ordering="connection_branch_name")
    def connection(self, obj: SuperAgent):
        return obj.connection_branch.link(from_agent=obj.pk)

    @admin.display(description="Output Type", ordering="output_type_branch_name")
    def output_type(self, obj: SuperAgent):
        return obj.output_type_branch.link(from_agent=obj.pk)

    @admin.display(
        description="Sampling Params", ordering="sampling_params_branch_name"
    )
    def sampling_params(self, obj: SuperAgent):
        return obj.sampling_params_branch.link(from_agent=obj.pk)

    @admin.display(description="Tool Group", ordering="tool_group_branch_name")
    def tool_group(self, obj: SuperAgent):
        return obj.tool_group_branch.link(from_agent=obj.pk)

    def template_selectors(self) -> list[dict[str, Any]]:
        return [
            {
                "key": "agent",
                "target": "#id_template",
                "field_prefix": "",
                "maps": {
                    relation: f"{relation}_template" for relation in agent_relations
                },
            }
        ] + [
            {
                "key": relation,
                "target": f"#id_{relation}_template",
                "field_prefix": f"{relation}_",
            }
            for relation in agent_relations
        ]

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)
        return qs_super_agent(qs, request.user.username)


@admin.register(SharedSuperAgent)
class SharedSuperAgentAdmin(SuperAgentAdmin):
    list_display = list(BranchModelAdmin.list_display) + [
        "owner",
        "instructions",
        "connection",
        "output_type",
        "sampling_params",
        "tool_group",
        "collaborators_csv",
    ]

    def get_queryset(self, request: HttpRequest):
        qs = (
            super(TypedModelAdmin, self)
            .get_queryset(request)
            .filter(collaborators__name=request.user.username)
        )
        return qs_super_agent(qs, request.user.username)
