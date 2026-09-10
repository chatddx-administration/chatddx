# src/chatddx/django/portal/forms/sampling_params.py

from typing import final

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django.forms import (
    CharField,
    ChoiceField,
    DecimalField,
    IntegerField,
)
from unfold.layout import Hr
from unfold.widgets import (
    UnfoldAdminDecimalFieldWidget,
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminIntegerFieldWidget,
    UnfoldAdminTextInputWidget,
)

from chatddx.django.portal.forms.base import BaseForm
from chatddx.django.portal.forms.widgets import TemplateSelectWidget
from chatddx.repo import proxies
from chatddx.repo.form_data_in import SamplingParamsFormDataIn
from chatddx.repo.form_data_out import SamplingParamsFormDataOut


@final
class SamplingParamsForm(BaseForm):
    form_data_in = SamplingParamsFormDataIn
    form_data_out = SamplingParamsFormDataOut
    bundle_name = "sampling_params"

    @final
    class Meta(BaseForm.Meta):
        model = proxies.SamplingParams

    name = CharField(
        max_length=255,
        widget=UnfoldAdminTextInputWidget(
            attrs={"placeholder": 'e.g., "seed-locked low-reasoning"'}
        ),
        label="Name",
    )
    template = ChoiceField(
        required=False,
        widget=TemplateSelectWidget(),
        label="Auto-fill from existing sampling params",
        help_text="This will overwrite all edited values in the sampling params section!",
    )
    temperature = DecimalField(
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(),
        label="Temperature",
    )
    top_p = DecimalField(
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(),
        label="Top P",
    )
    top_k = IntegerField(
        required=False,
        widget=UnfoldAdminIntegerFieldWidget(),
        label="Top K",
    )
    max_tokens = IntegerField(
        required=False,
        widget=UnfoldAdminIntegerFieldWidget(),
        label="Max Tokens",
    )
    seed = IntegerField(
        required=False,
        widget=UnfoldAdminIntegerFieldWidget(),
        label="Seed",
    )
    n = IntegerField(
        required=False,
        widget=UnfoldAdminIntegerFieldWidget(),
        label="N (Choices)",
    )
    presence_penalty = DecimalField(
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(),
        label="Presence Penalty",
    )
    frequency_penalty = DecimalField(
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(),
        label="Frequency Penalty",
    )
    stop_sequences = CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(),
        label="Stop Sequences",
    )
    logit_bias = CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(),
        label="Logit Bias",
    )
    provider_params = CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(),
        label="Additional Params",
    )

    helper = FormHelper()
    helper.form_tag = False
    helper.include_media = False
    helper.layout = Layout(
        Fieldset(
            "Sampling Parameters",
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
                    Row("temperature"),
                    Row("seed"),
                ),
                Column(
                    Row("max_tokens"),
                    Row("n"),
                ),
                Column(
                    Row("presence_penalty"),
                    Row("frequency_penalty"),
                ),
                Column(
                    Row("top_p"),
                    Row("top_k"),
                ),
            ),
            Hr(),
            Row(
                Column("stop_sequences"),
                Column("logit_bias"),
                Column("provider_params"),
            ),
            css_class="mb-8",
        )
    )
