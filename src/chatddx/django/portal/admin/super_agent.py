# pyright: basic
import json
from typing import Any, override

from django.contrib import admin
from django.http import HttpRequest

from chatddx.django.portal.admin.base import BranchModelAdmin, TypedModelAdmin
from chatddx.django.portal.admin.utils import get_branch_link
from chatddx.django.portal.forms import (
    SuperAgentForm,
)
from chatddx.repo import proxies
from chatddx.repo.shufflers.main import (
    agent_relations,
    load_template_data,
    qs_super_agent,
)


@admin.register(proxies.SuperAgent)
class SuperAgentAdmin(BranchModelAdmin[proxies.SuperAgent]):
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
    def instructions(self, obj: proxies.Agent) -> str:
        return str(obj.target.instructions[:20])  # pyright: ignore

    @admin.display(description="Connection", ordering="connection_name")
    def connection(self, obj: proxies.Agent):
        return get_branch_link(obj, "connection")

    @admin.display(description="Output Type", ordering="output_type_name")
    def output_type(self, obj: proxies.Agent):
        return get_branch_link(obj, "output_type")

    @admin.display(description="Sampling Params", ordering="sampling_params_name")
    def sampling_params(self, obj: proxies.Agent):
        return get_branch_link(obj, "sampling_params")

    @admin.display(description="Tool Group", ordering="tool_group_name")
    def tool_group(self, obj: proxies.Agent):
        return get_branch_link(obj, "tool_group")

    @override
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
            "template_data": load_template_data(owner).model_dump_json(by_alias=True),
            "form_info": json.dumps(form_info),
        }

    def get_object(self, request: HttpRequest, object_id: str, from_field: None = None):
        obj = super().get_object(request, object_id, from_field)
        return obj

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)
        return qs_super_agent(qs, request.user.username)


@admin.register(proxies.SharedSuperAgent)
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
