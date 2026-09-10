# src/chatddx/django/portal/forms/tool_group.py
from typing import Any, final, override

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django.forms import (
    CharField,
    ModelChoiceField,
)
from unfold.fields import ModelMultipleChoiceField
from unfold.layout import Hr
from unfold.widgets import (
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminSelectMultipleWidget,
    UnfoldAdminTextInputWidget,
)

from chatddx.django.orm.qs import qs_canon, qs_owned_trails
from chatddx.django.portal.forms.base import BaseForm
from chatddx.django.portal.forms.widgets import TemplateSelectWidget
from chatddx.repo import proxies
from chatddx.repo.form_data_in import ToolGroupFormDataIn
from chatddx.repo.form_data_out import ToolGroupFormDataOut
from chatddx.repo.trail_models import ToolTrailModel


@final
class ToolGroupForm(BaseForm):
    form_data_in = ToolGroupFormDataIn
    form_data_out = ToolGroupFormDataOut
    bundle_name = "tool_group"

    @final
    class Meta(BaseForm.Meta):
        model = proxies.ToolGroup

    def __init__(self, *args: Any, **kwargs: Any):
        request = kwargs["request"]

        super().__init__(*args, **kwargs)
        self.fields["tools"].queryset = qs_owned_trails(  # pyright: ignore[reportAttributeAccessIssue]
            ToolTrailModel.objects.all(), request.user.username
        )

    @override
    def clean(self):
        cleaned = super().clean()
        return cleaned

    name = CharField(
        max_length=255,
        widget=UnfoldAdminTextInputWidget(
            attrs={"placeholder": "e.g., Web Search & Math Suite"}
        ),
        label="Tool Group Name",
        help_text="Create a new tool group, or enter an existing name to update it. The latest save becomes the active version.",
    )
    template = ModelChoiceField(
        queryset=proxies.ToolGroup.objects.none(),
        required=False,
        empty_label="--- Start from scratch ---",
        widget=TemplateSelectWidget(),
        label="Tool Group Template",
        help_text="Optional. Select a pre-configured template to populate the tools and instructions below.",
    )
    tools = ModelMultipleChoiceField(
        queryset=ToolTrailModel.objects.none(),
        widget=UnfoldAdminSelectMultipleWidget(),
        required=False,
        label="Available Tools",
        help_text="Select the specific functions, APIs, or integrations this agent is permitted to execute.",
    )
    instructions = CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(
            attrs={
                "placeholder": "e.g., Always use the web search tool before answering factual questions. Do not use the calculator for simple arithmetic."
            }
        ),
        label="Tool Usage Instructions",
        help_text="Specific guidelines dictating exactly when and how the agent should utilize the selected tools. This is appended to the main system prompt.",
    )

    helper = FormHelper()
    helper.include_media = False
    helper.form_tag = False

    helper.layout = Layout(
        Fieldset(
            "Tool Group Settings",
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
            Hr(),
            Row(
                Column(
                    "instructions",
                    css_class="w-1/2",
                ),
                Column(
                    "tools",
                    css_class="w-1/2",
                ),
            ),
        ),
    )
