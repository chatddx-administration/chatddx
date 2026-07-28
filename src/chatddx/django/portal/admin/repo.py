# pyright: basic
import json
from typing import Any, final, override

from django.contrib import admin
from django.http import HttpRequest
from django.urls import reverse
from unfold.utils import format_html

from chatddx.django.portal.admin.base import BranchModelAdmin, TypedModelAdmin
from chatddx.django.portal.forms import (
    AgentForm,
    ConnectionForm,
    OutputTypeForm,
    SamplingParamsForm,
    SuperAgentForm,
    ToolGroupForm,
)
from chatddx.django.portal.forms.tool import ToolForm
from chatddx.repo import proxies
from chatddx.repo.base import BranchModel
from chatddx.repo.shufflers.main import (
    agent_relations,
    load_template_data,
    qs_super_agent,
)


def get_branch_link(obj: BranchModel, field_name: str):
    branch_id = getattr(obj, f"{field_name}_id")
    branch_name = getattr(obj, f"{field_name}_name")
    target = getattr(obj.target, field_name)
    label = branch_name or target.fingerprint[:6]
    if branch_id:
        url = (
            reverse(
                f"admin:orm_{field_name.replace('_', '')}_change",
                args=[branch_id],
            )
            + f"?from_agent={obj.pk}"
        )
    else:
        url = (
            reverse(
                f"admin:orm_{field_name.replace('_', '')}_add",
            )
            + f"?from_agent={obj.pk}&target={target.id}"
        )

    return format_html('<a href="{}">{}</a>', url, label)


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


@admin.register(proxies.Connection)
class ConnectionAdmin(BranchModelAdmin[proxies.Connection]):
    form = ConnectionForm
    name = "connection"

    list_display = BranchModelAdmin.list_display + [  # pyright: ignore
        "name",
        "_model",
        "provider",
        "endpoint",
    ]

    @admin.display(description="Model", ordering="target__model")
    def _model(self, obj: proxies.Connection) -> str:
        return obj.target.model  # pyright: ignore

    @admin.display(description="Endpoint", ordering="target__endpoint")
    def endpoint(self, obj: proxies.Connection) -> str:
        return obj.target.endpoint  # pyright: ignore

    @admin.display(description="Provider", ordering="target__provider")
    def provider(self, obj: proxies.Connection) -> str:
        return obj.target.get_provider_display()  # pyright: ignore


@final
@admin.register(proxies.SamplingParams)
class SamplingParamsAdmin(BranchModelAdmin[proxies.SamplingParams]):
    form = SamplingParamsForm
    name = "sampling_params"

    list_display = BranchModelAdmin.list_display + [  # pyright: ignore
        "name",
        "seed",
        "temperature",
        "top_p",
    ]

    @admin.display(description="Seed", ordering="target__seed")
    def seed(self, obj: proxies.SamplingParams) -> str:
        return str(obj.target.seed)  # pyright: ignore

    @admin.display(description="Temp", ordering="target__temperature")
    def temperature(self, obj: proxies.SamplingParams) -> str:
        return str(obj.target.temperature)  # pyright: ignore

    @admin.display(description="Top-p", ordering="target__top_p")
    def top_p(self, obj: proxies.SamplingParams) -> str:
        return str(obj.target.top_p)  # pyright: ignore


@final
@admin.register(proxies.OutputType)
class OutputTypeAdmin(BranchModelAdmin[proxies.OutputType]):
    form = OutputTypeForm
    name = "output_type"

    list_display = BranchModelAdmin.list_display + [  # pyright: ignore
        "name",
        "_type",
        "validation_strategy",
        "coercion_strategy",
    ]

    @admin.display(
        description="Coercion Strategy",
        ordering="target__coercion_strategy",
    )
    def coercion_strategy(self, obj: proxies.OutputType) -> str:
        return obj.target.get_coercion_strategy_display()  # pyright: ignore

    @admin.display(
        description="Type",
        ordering="target__definition",
    )
    def _type(self, obj: proxies.OutputType) -> str:
        return obj.target.definition.get("type", None)  # pyright: ignore

    @admin.display(
        description="Validation Strategy",
        ordering="target__validation_strategy",
    )
    def validation_strategy(self, obj: proxies.OutputType) -> str:
        return obj.target.get_validation_strategy_display()  # pyright: ignore


@final
@admin.register(proxies.ToolGroup)
class ToolGroupAdmin(BranchModelAdmin[proxies.ToolGroup]):
    form = ToolGroupForm
    name = "tool_group"
    list_display = BranchModelAdmin.list_display + []  # pyright: ignore


@final
@admin.register(proxies.Tool)
class ToolAdmin(BranchModelAdmin[proxies.Tool]):
    form = ToolForm
    name = "tool"

    list_display = BranchModelAdmin.list_display + [  # pyright: ignore
        "type",
    ]

    @admin.display(
        description="Type",
        ordering="target__type",
    )
    def type(self, obj: proxies.Tool) -> str:
        return obj.target.get_type_display()  # pyright: ignore
