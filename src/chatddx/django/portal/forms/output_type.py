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
from chatddx.django.portal.forms.widgets import TemplateSelectWidget
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
        widget=UnfoldAdminTextInputWidget(),
        label="Name",
    )
    template = ChoiceField(
        required=False,
        widget=TemplateSelectWidget(),
        label="Auto-fill from existing output type",
        help_text="This will overwrite all edited values in the output type section!",
    )
    output_retries = IntegerField(
        widget=UnfoldAdminIntegerFieldWidget(),
        label="Output Retries",
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
        help_text="How the model is forced to follow the schema (system prompts, guided decoding, or tool call).",
    )
    definition = CharField(
        required=False,
        widget=UnfoldAdminTextareaWidget(attrs={"placeholder": "[free text]"}),
        label="Schema Definition",
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
