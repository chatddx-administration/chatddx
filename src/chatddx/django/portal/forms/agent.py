# src/chatddx/django/portal/admin/forms/agent.py
# pyright: basic
from typing import Any, final

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django import forms
from unfold.admin import messages
from unfold.widgets import (
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminSelect2MultipleWidget,
    UnfoldAdminSelect2Widget,
    UnfoldAdminTextInputWidget,
)

from chatddx.core.models import IdentityModel
from chatddx.django.portal.forms.base import BaseForm
from chatddx.repo import proxies
from chatddx.repo.branch_spec import AgentBranchSpec
from chatddx.repo.form_data_in import AgentFormDataIn
from chatddx.repo.form_data_out import AgentFormDataOut
from chatddx.repo.shufflers.main import (
    agent_relations,
    dump_branch,
    load_branch,
    load_form_data,
    qs_canon,
    qs_owned_trails,
)
from chatddx.repo.trail_models import (
    ConnectionTrailModel,
    OutputTypeTrailModel,
    SamplingParamsTrailModel,
    ToolGroupTrailModel,
    ToolTrailModel,
)


@final
class AgentForm(BaseForm):
    form_data_in = AgentFormDataIn
    form_data_out = AgentFormDataOut
    bundle_name = "agent"

    @final
    class Meta(BaseForm.Meta):
        model = proxies.Agent

    def __init__(self, *args: Any, **kwargs: Any):
        request = kwargs["request"]

        super().__init__(*args, **kwargs)

        owner = request.user.username
        owned = qs_canon(proxies.Agent.objects.all(), owner)

        self.fields["template"].choices = [("", "=== clear ===")] + [
            (model.target.pk, model.name) for model in owned
        ]

        self.fields["connection"].queryset = qs_owned_trails(
            ConnectionTrailModel.objects.all(), owner
        )
        self.fields["sampling_params"].queryset = qs_owned_trails(
            SamplingParamsTrailModel.objects.all(), owner
        )
        self.fields["output_type"].queryset = qs_owned_trails(
            OutputTypeTrailModel.objects.all(), owner
        )
        self.fields["tool_group"].queryset = qs_owned_trails(
            ToolGroupTrailModel.objects.all(), owner
        )

    def get_initial(self, instance: proxies.Agent):
        instance.target.tool_group.tools = list(
            ToolTrailModel.objects.filter(pk__in=instance.target.tool_group.tools)
        )

        agent_spec_dict = AgentBranchSpec.model_validate(instance).model_dump()

        agent_dict = AgentFormDataOut.model_validate(
            agent_spec_dict | agent_spec_dict["target"]
        ).model_dump(by_alias=True)

        relations_dict: dict[str, Any] = {}
        owner_name = self.request.user.username

        for relation in agent_relations:
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
                relations_dict[relation] = load_form_data(
                    branch=branch_model
                ).model_dump(by_alias=True)
                messages.info(
                    self.request,
                    f"Recreated a branch for trail '{relation}' with fingerprint '{relation_trail.fingerprint[:6]}' fyi 👇",
                )

        return agent_dict | {
            name: values["pk"] for name, values in relations_dict.items()
        }

    def clean_tool_group(self):
        tool_group = self.cleaned_data["tool_group"]
        tool_group.tools = list(ToolTrailModel.objects.filter(pk__in=tool_group.tools))
        return tool_group

    name = forms.CharField(
        max_length=255,
        widget=UnfoldAdminTextInputWidget(),
        label="Agent name",
        help_text="Create a new agent, or enter an existing name to update it. The latest save becomes the active version.",
    )
    template = forms.ChoiceField(
        required=False,
        widget=UnfoldAdminSelect2Widget(),
        label="Base Template",
        help_text="Optional. Select a pre-configured template to quickly populate the settings below.",
    )
    instructions = forms.CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(
            attrs={"placeholder": "No instructions provided"}
        ),
        label="System instructions",
        help_text="The core system prompt that dictates the agent's persona, rules, and boundaries.",
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
    connection = forms.ModelChoiceField(
        queryset=ConnectionTrailModel.objects.none(),
        widget=UnfoldAdminSelect2Widget(),
        label="Connection",
    )
    sampling_params = forms.ModelChoiceField(
        queryset=SamplingParamsTrailModel.objects.none(),
        widget=UnfoldAdminSelect2Widget(),
        label="Sampling Parameters",
    )
    output_type = forms.ModelChoiceField(
        queryset=OutputTypeTrailModel.objects.none(),
        widget=UnfoldAdminSelect2Widget(),
        label="Output Type",
    )
    tool_group = forms.ModelChoiceField(
        queryset=ToolGroupTrailModel.objects.none(),
        widget=UnfoldAdminSelect2Widget(),
        label="Tool Group",
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
                    "collaborators",
                    css_class="w-1/2",
                ),
            ),
            Row(
                Column(
                    "owner",
                ),
                css_class="w-1/2",
            ),
            css_class="mb-8",
        )
        relations_section = Fieldset(
            "Agent Relations",
            Row(
                Column(
                    "connection",
                    "sampling_params",
                    css_class="w-1/2",
                ),
                Column(
                    "output_type",
                    "tool_group",
                    css_class="w-1/2",
                ),
            ),
            css_class="mb-8",
        )

        helper.layout = Layout(main_section, relations_section)

        return helper
