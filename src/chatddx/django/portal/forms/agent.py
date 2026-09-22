# pyright: basic
from typing import Any

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django import forms
from unfold.widgets import (
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminSelect2MultipleWidget,
    UnfoldAdminSelect2Widget,
    UnfoldAdminTextInputWidget,
)

from chatddx.core.models import IdentityModel
from chatddx.django.orm.qs import qs_owned_trails
from chatddx.django.portal.forms.branch_base import BranchForm
from chatddx.django.portal.forms.widgets import TemplateSelectWidget
from chatddx.repo.entities.agent.django import Agent
from chatddx.repo.entities.agent.pydantic import (
    AgentBranchSpec,
    AgentFormDataOut,
)
from chatddx.repo.entities.connection.django import ConnectionTrailModel
from chatddx.repo.entities.output_type.django import OutputTypeTrailModel
from chatddx.repo.entities.sampling_params.django import SamplingParamsTrailModel
from chatddx.repo.entities.tool.django import ToolTrailModel
from chatddx.repo.entities.tool_group.django import ToolGroupTrailModel


class AgentForm(BranchForm):
    entity_name = "agent"

    class Meta(BranchForm.Meta):
        model = Agent

    def __init__(self, *args: Any, **kwargs: Any):
        request = kwargs["request"]

        super().__init__(*args, **kwargs)

        owner = request.user.username

        self.fields["connection"].queryset = qs_owned_trails(  # pyright: ignore[reportAttributeAccessIssue]
            ConnectionTrailModel.objects.all(), owner
        )
        self.fields["sampling_params"].queryset = qs_owned_trails(  # pyright: ignore[reportAttributeAccessIssue]
            SamplingParamsTrailModel.objects.all(), owner
        )
        self.fields["output_type"].queryset = qs_owned_trails(  # pyright: ignore[reportAttributeAccessIssue]
            OutputTypeTrailModel.objects.all(), owner
        )
        self.fields["tool_group"].queryset = qs_owned_trails(  # pyright: ignore[reportAttributeAccessIssue]
            ToolGroupTrailModel.objects.all(), owner
        )

    def get_initial(self, instance: Agent):
        instance.target.tool_group.tools = list(  # pyright: ignore[reportAttributeAccessIssue]
            ToolTrailModel.objects.filter(pk__in=instance.target.tool_group.tools)
        )

        agent_spec_dict = AgentBranchSpec.model_validate(instance).model_dump()

        return AgentFormDataOut.model_validate(
            agent_spec_dict | agent_spec_dict["target"]
        ).model_dump(by_alias=True)

    def clean_tool_group(self):
        tool_group = self.cleaned_data["tool_group"]
        tool_group.tools = list(ToolTrailModel.objects.filter(pk__in=tool_group.tools))
        return tool_group

    name = forms.CharField(
        max_length=255,
        widget=UnfoldAdminTextInputWidget(),
        label="Name",
    )
    template = forms.ChoiceField(
        required=False,
        widget=TemplateSelectWidget(),
        label="Auto-fill from existing agent",
        help_text="This will overwrite all edited values!",
    )
    # the agent's instruction, as the text it is a bundle of
    instruction = forms.CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(),
        label="Instructions",
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
            "Simple Agent Settings",
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
                    "owner",
                    css_class="w-1/2",
                ),
                Column(
                    "collaborators",
                    css_class="w-1/2",
                ),
            ),
            Row(
                Column(
                    "instruction",
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
