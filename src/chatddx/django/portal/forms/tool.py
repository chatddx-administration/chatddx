# src/chatddx/django/portal/forms/tool.py

from typing import final

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django.forms import (
    CharField,
    ChoiceField,
    ModelChoiceField,
)
from unfold.layout import Hr
from unfold.widgets import (
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminSelect2Widget,
    UnfoldAdminTextInputWidget,
)

from chatddx.core.choices import ToolChoices
from chatddx.django.portal.forms.base import BaseForm
from chatddx.django.portal.forms.widgets import TemplateSelectWidget
from chatddx.repo import proxies
from chatddx.repo.form_data_in import ToolFormDataIn
from chatddx.repo.form_data_out import ToolFormDataOut


@final
class ToolForm(BaseForm):
    form_data_in = ToolFormDataIn
    form_data_out = ToolFormDataOut
    bundle_name = "tool"

    @final
    class Meta(BaseForm.Meta):
        model = proxies.Tool

    name = CharField(
        max_length=255,
        widget=UnfoldAdminTextInputWidget(),
        label="Tool Name",
        help_text="Create a new tool, or enter an existing name to update it. The latest save becomes the active version.",
    )
    template = ModelChoiceField(
        queryset=proxies.Tool.objects.none(),
        required=False,
        empty_label="--- Start from scratch ---",
        widget=TemplateSelectWidget(),
        label="Tool Template",
        help_text="Optional. Select a pre-configured template to populate the tools and instructions below.",
    )
    command = CharField(
        max_length=255,
        widget=UnfoldAdminTextInputWidget(),
        label="Command",
        help_text="The exact model identifier required by your chosen provider.",
    )
    type = ChoiceField(
        choices=ToolChoices.choices,
        widget=UnfoldAdminSelect2Widget(),
        label="Tool Type",
        help_text="The service hosting the selected model.",
    )
    parameters = CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(),
        label="Parameter Definition (TOML)",
        help_text="Define the required JSONSchema output structure using TOML formatting.",
    )

    helper = FormHelper()
    helper.include_media = False
    helper.form_tag = False

    helper.layout = Layout(
        Fieldset(
            "Tool Settings",
            Row(
                Column(
                    Row("name"),
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
                    Row("command"),
                    Row("type"),
                    css_class="w-1/2",
                ),
                Column(
                    "parameters",
                    css_class="w-1/2",
                ),
            ),
        ),
    )
