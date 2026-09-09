# src/chatddx/django/portal/forms/output_type.py

from typing import final

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django.forms import (
    CharField,
    ChoiceField,
    IntegerField,
    ModelChoiceField,
)
from unfold.layout import Hr
from unfold.widgets import (
    UnfoldAdminIntegerFieldWidget,
    UnfoldAdminSelect2Widget,
    UnfoldAdminTextareaWidget,
    UnfoldAdminTextInputWidget,
)

from chatddx.core.choices import CoercionChoices, ValidationChoices
from chatddx.django.portal.forms.base import BaseForm
from chatddx.repo import proxies
from chatddx.repo.form_data_in import OutputTypeFormDataIn
from chatddx.repo.form_data_out import OutputTypeFormDataOut


@final
class OutputTypeForm(BaseForm):
    form_data_in = OutputTypeFormDataIn
    form_data_out = OutputTypeFormDataOut
    bundle_name = "output_type"

    @final
    class Meta(BaseForm.Meta):
        model = proxies.OutputType

    name = CharField(
        max_length=255,
        widget=UnfoldAdminTextInputWidget(
            attrs={"placeholder": "e.g., JSON User Profile Extractor"}
        ),
        label="Output Profile Name",
        help_text="Create a new output profile, or enter an existing name to update it. The latest save becomes the active version.",
    )
    template = ModelChoiceField(
        queryset=proxies.OutputType.objects.none(),
        required=False,
        widget=UnfoldAdminSelect2Widget(),
        label="Output Template",
        help_text="Use this to select a pre-configured template to populate the schema and strategies below, the value of this field will not be included in the form.",
    )
    output_retries = IntegerField(
        widget=UnfoldAdminIntegerFieldWidget(),
        label="Output Retries",
        help_text="Number of attempts to generate correct output, applies unconditionally to parsing error and also validation if set to 'retry' below.",
    )
    validation_strategy = ChoiceField(
        choices=ValidationChoices.choices,
        widget=UnfoldAdminSelect2Widget(),
        label="Validation Strategy",
        help_text="What to do when schema validation fails, if set to 'retry' make sure to set 'output_retries' to something meaningful, as the default (1) is equivalent to 'crash'",
    )
    coercion_strategy = ChoiceField(
        choices=CoercionChoices.choices,
        widget=UnfoldAdminSelect2Widget(),
        label="Coerceion Strategy",
        help_text="How the model is forced to follow the schema (e.g., via System Prompts, Native JSON decoding, or Tool/Function Calling).",
    )
    definition = CharField(
        required=False,
        widget=UnfoldAdminTextareaWidget(
            attrs={
                "placeholder": 'type = "object"\n\n[properties.summary]\ntype = "string"\n\n[properties.score]\ntype = "number"'
            }
        ),
        label="Schema Definition (TOML)",
        help_text="Define the required JSONSchema output structure using TOML formatting. Leave blank to accept unstructured plain text.",
    )

    helper = FormHelper()
    helper.form_tag = False
    helper.include_media = False

    helper.layout = Layout(
        Fieldset(
            "Output Structure",
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
                    Row("output_retries"),
                    Row("validation_strategy"),
                    Row("coercion_strategy"),
                    css_class="w-1/2",
                ),
                Column(
                    Row("definition"),
                    css_class="w-1/2",
                ),
            ),
            css_class="mb-8",
        ),
    )
