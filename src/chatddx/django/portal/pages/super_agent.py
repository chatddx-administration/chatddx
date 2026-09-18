# pyright: basic

import json
from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from chatddx.django.orm.qs import qs_super_agent
from chatddx.django.portal.branch import BranchModelAdmin
from chatddx.django.portal.forms.super_agent import SuperAgentForm
from chatddx.django.portal.typing import TypedModelAdmin
from chatddx.django.portal.utils import (
    get_branch_link,
    inventory_form_data_out,
    truncate_for_list_display,
)
from chatddx.repo.entities.agent.django import Agent
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

    @admin.display(description="Instructions", ordering="target__instructions")
    def instructions(self, obj: Agent) -> str:
        return truncate_for_list_display(obj.target.instructions)

    @admin.display(description="Connection", ordering="connection_name")
    def connection(self, obj: Agent):
        return get_branch_link(obj, "connection")

    @admin.display(description="Output Type", ordering="output_type_name")
    def output_type(self, obj: Agent):
        return get_branch_link(obj, "output_type")

    @admin.display(description="Sampling Params", ordering="sampling_params_name")
    def sampling_params(self, obj: Agent):
        return get_branch_link(obj, "sampling_params")

    @admin.display(description="Tool Group", ordering="tool_group_name")
    def tool_group(self, obj: Agent):
        return get_branch_link(obj, "tool_group")

    def get_form_context(
        self,
        request: HttpRequest,
        obj: Any,
    ) -> dict[str, Any]:
        owner = request.user.username

        form_info: dict[str, Any] = {
            "template_selectors": [
                {
                    "key": "agent",
                    "target": "#id_template",
                    "field_prefix": "",
                    "maps": {
                        "connection": "connection_template",
                        "sampling_params": "sampling_params_template",
                        "output_type": "output_type_template",
                        "tool_group": "tool_group_template",
                    },
                }
            ]
            + [
                {
                    "key": model,
                    "target": f"#id_{model}_template",
                    "field_prefix": model + "_",
                }
                for model in agent_relations
            ]
        }

        return {
            "template_data": inventory_form_data_out(owner),
            "form_info": json.dumps(form_info),
        }

    def get_object(self, request: HttpRequest, object_id: str, from_field: None = None):
        obj = super().get_object(request, object_id, from_field)
        return obj

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
