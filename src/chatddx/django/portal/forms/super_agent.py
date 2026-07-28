# src/chatddx/django/portal/forms/super_agent.py
# pyright: basic
from copy import deepcopy
from typing import Any, final, override

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, LayoutObject, Row
from django import forms
from django.http.request import QueryDict
from unfold.admin import messages
from unfold.widgets import (
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminSelect2MultipleWidget,
    UnfoldAdminSelect2Widget,
    UnfoldAdminTextInputWidget,
)

from chatddx.core.models import IdentityModel
from chatddx.django.portal.forms.base import BaseForm
from chatddx.django.portal.forms.connection import ConnectionForm
from chatddx.django.portal.forms.output_type import OutputTypeForm
from chatddx.django.portal.forms.sampling_params import SamplingParamsForm
from chatddx.django.portal.forms.tool_group import ToolGroupForm
from chatddx.repo import proxies
from chatddx.repo.branch_spec import AgentBranchSpec
from chatddx.repo.form_data_in import SuperAgentFormDataIn
from chatddx.repo.form_data_out import SuperAgentFormDataOut
from chatddx.repo.main import BundleName
from chatddx.repo.shufflers.main import (
    agent_relations,
    dump_branch,
    load_branch,
    load_form_data,
)
from chatddx.repo.trail_models import ToolTrailModel

OPTIONAL_FIELDS = {
    "connection_name",
    "sampling_params_name",
    "output_type_name",
    "tool_group_name",
}

SUBFORMS: list[tuple[BundleName, type[BaseForm]]] = [
    ("connection", ConnectionForm),
    ("sampling_params", SamplingParamsForm),
    ("output_type", OutputTypeForm),
    ("tool_group", ToolGroupForm),
]


def apply_prefix_to_layout(layout_node: LayoutObject, prefix: str):
    for i, item in enumerate(layout_node.fields):
        if isinstance(item, str):
            layout_node.fields[i] = prefixed(item, prefix)
        elif hasattr(item, "fields"):
            apply_prefix_to_layout(item, prefix)

    return layout_node


def prefixed(name: str, prefix: str):
    return f"{prefix}_{name}"


def unprefixed(name: str, prefix: str):
    return name[len(prefix) + 1 :]


def get_subform_data(data: QueryDict, prefix: str) -> QueryDict | None:
    if not data:
        return None
    result = QueryDict(mutable=True)
    for k, vals in data.lists():
        if k.startswith(prefix):
            result.setlist(unprefixed(k, prefix), vals)
    return result


def flatten_form_data(data: dict[str, Any]):
    return {
        prefixed(field_name, prefix): value
        for prefix, subform in data.items()
        for field_name, value in subform.items()
    }


@final
class SuperAgentForm(BaseForm):
    @final
    class Meta(BaseForm.Meta):
        model = proxies.Agent

    form_data_in = SuperAgentFormDataIn
    form_data_out = SuperAgentFormDataOut
    bundle_name = "agent"

    subforms: dict[BundleName, BaseForm]

    @override
    def save(self, commit: bool = True) -> Any:
        instance = super().save(commit=commit)
        if instance and instance.get("api_key") and self.validated_data:
            owner = self.validated_data.owner
            owner_api_keys = owner.secrets.get("api-keys", {})
            agent_name = self.validated_data.name
            current_api_key = owner_api_keys.get(agent_name, None)

            if instance["api_key"] == current_api_key:
                messages.info(
                    self.request,
                    f"The provided API-key matches the current API-key for identity {owner.name}, all good.",
                )
            else:
                owner.secrets["api-keys"] = owner_api_keys | {
                    agent_name: instance["api_key"]
                }
                owner.save()
                messages.success(
                    self.request,
                    f"Updated API-key for identity {owner.name} and connection {agent_name}.",
                )

    @override
    def clean(self):
        for subform_name, subform_instance in self.subforms.items():
            is_valid = subform_instance.is_valid()
            self.cleaned_data[subform_name] = subform_instance.clean()

            if not is_valid:
                for field_name, error_messages in subform_instance.errors.items():
                    for error_msg in error_messages:
                        self.add_error(prefixed(field_name, subform_name), error_msg)

        cleaned = super().clean()
        return cleaned

    def __init__(self, *args: Any, **kwargs: Any):
        self.subforms = {}
        self.request = kwargs["request"]

        super().__init__(*args, **kwargs)

        if self.data:
            self.data = self.data.copy()
            self.data.pop("agent_template", None)
            for field_name in agent_relations:
                self.data.pop(f"{field_name}_template", None)

        for prefix, cls in SUBFORMS:
            sub_form_data = get_subform_data(self.data, prefix)
            self.subforms[prefix] = cls(
                data=sub_form_data,
                request=self.request,
            )
            for _name, _field in self.subforms[prefix].fields.items():
                name = prefixed(_name, prefix)
                field = deepcopy(_field)

                if name in OPTIONAL_FIELDS:
                    field.required = False

                self.fields[name] = field

    def get_initial(self, instance: proxies.SuperAgent):

        instance.target.tool_group.tools = list(
            ToolTrailModel.objects.filter(pk__in=instance.target.tool_group.tools)
        )

        agent_spec_dict = AgentBranchSpec.model_validate(instance).model_dump()

        agent_dict = SuperAgentFormDataOut.model_validate(
            agent_spec_dict | agent_spec_dict["target"]
        ).model_dump(by_alias=True)

        relations_dict: dict[str, Any] = {}
        owner_name = self.request.user.username

        for relation, _ in SUBFORMS:
            agent_trail = instance.target
            branch_model = load_branch(
                bundle_name=relation,
                owner_name=owner_name,
                trail=getattr(agent_trail, relation),
            )
            if branch_model is None:
                relation_trail = getattr(agent_trail, relation)
                branch_name = str(relation_trail.fingerprint)[:6]
                branch_model, _ = dump_branch(
                    relation,
                    branch_name,
                    owner_name,
                    relation_trail,
                )
                messages.info(
                    self.request,
                    f"Recreated a branch for trail '{relation}' with fingerprint '{relation_trail.fingerprint[:6]}' fyi 👇",
                )

            relations_dict[relation] = load_form_data(branch_model).model_dump(
                by_alias=True
            )

        initial = agent_dict | flatten_form_data(relations_dict)
        return initial

    name = forms.CharField(
        max_length=255,
        widget=UnfoldAdminTextInputWidget(),
        label="Agent name",
        help_text="Create a new agent, or enter an existing name to update it. The latest save becomes the active version.",
    )
    template = forms.ModelChoiceField(
        queryset=proxies.Agent.objects.none(),
        required=False,
        empty_label="--- Start from scratch ---",
        widget=UnfoldAdminSelect2Widget(),
        label="Base Template",
        help_text="Optional. Select a pre-configured template to quickly populate the settings below.",
    )
    api_key = forms.CharField(
        max_length=255,
        required=False,
        widget=UnfoldAdminTextInputWidget(
            attrs={"placeholder": "Enter key or leave blank to use existing"}
        ),
        label="API Key",
        help_text="Stored securely under your personal user account. It is <strong>not</strong> saved in the shared version history.",
    )
    collaborators = forms.ModelMultipleChoiceField(
        required=False,
        queryset=IdentityModel.objects.all(),
        widget=UnfoldAdminSelect2MultipleWidget(),
        label="Collaborators",
    )
    owner = forms.ModelChoiceField(
        required=False,
        queryset=IdentityModel.objects.all(),
        widget=UnfoldAdminSelect2Widget(),
        label="Owner",
    )

    instructions = forms.CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(
            attrs={"placeholder": "No instructions provided"}
        ),
        label="System instructions",
        help_text="The core system prompt that dictates the agent's persona, rules, and boundaries.",
    )

    @property
    def helper(self):
        helper = FormHelper()

        helper.form_tag = False
        helper.include_media = False

        main_section = Fieldset(
            "Agent Settings",
            Row(
                Column(
                    "name",
                    css_class="w-1/2",
                ),
                Column(
                    "template",
                    css_class="w-1/2",
                ),
            ),
            Row(
                Column(
                    "instructions",
                    css_class="w-1/2",
                ),
                Column(
                    "api_key",
                    css_class="w-1/2",
                ),
            ),
            Row(
                Column(
                    "owner",
                    css_class="w-1/2",
                ),
                Column(
                    "collaborators",
                    css_class="w-1/2",
                ),
            ),
            css_class="mb-8",
        )

        helper.layout = Layout(main_section)
        for prefix, _ in SUBFORMS:
            subform_instance = self.subforms[prefix]

            helper.layout.append(
                apply_prefix_to_layout(
                    deepcopy(subform_instance.helper.layout[0]),
                    prefix,
                )
            )

        return helper
