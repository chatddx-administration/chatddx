# src/chatddx/django/portal/forms/sampling_params.py

from typing import final

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django.forms import (
    CharField,
    DecimalField,
    IntegerField,
    ModelChoiceField,
)
from unfold.layout import Hr
from unfold.widgets import (
    UnfoldAdminDecimalFieldWidget,
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminIntegerFieldWidget,
    UnfoldAdminSelect2Widget,
    UnfoldAdminTextInputWidget,
)

from chatddx.django.portal.forms.base import BaseForm
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
            attrs={"placeholder": "e.g., Default Creative Preset"}
        ),
        label="Profile Name",
        help_text="Create a new sampling profile, or enter an existing name to update it. The latest save becomes the active version.",
    )
    template = ModelChoiceField(
        queryset=proxies.SamplingParams.objects.none(),
        required=False,
        empty_label="--- Start from scratch ---",
        widget=UnfoldAdminSelect2Widget(),
        label="Sampling Template",
        help_text="Optional. Select a pre-configured template to populate the parameters below.",
    )
    temperature = DecimalField(
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(attrs={"placeholder": "0.7"}),
        label="Temperature",
        help_text="Controls randomness. Lower values (e.g., 0.2) are more focused and deterministic; higher values (e.g., 0.8) are more creative.",
    )
    top_p = DecimalField(
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(attrs={"placeholder": "1.0"}),
        label="Top P",
        help_text="Nucleus sampling. A value of 0.1 means only tokens comprising the top 10% probability mass are considered.",
    )
    top_k = IntegerField(
        required=False,
        widget=UnfoldAdminIntegerFieldWidget(attrs={"placeholder": "50"}),
        label="Top K",
        help_text="Limits the next-token selection to the K most probable tokens. (Note: Not supported by all providers).",
    )
    max_tokens = IntegerField(
        required=False,
        widget=UnfoldAdminIntegerFieldWidget(attrs={"placeholder": "2048"}),
        label="Max Tokens",
        help_text="The absolute maximum number of tokens the model can generate in a single response.",
    )
    seed = IntegerField(
        required=False,
        widget=UnfoldAdminIntegerFieldWidget(attrs={"placeholder": "1337"}),
        label="Seed",
        help_text="Set a specific integer to make generation deterministic. Useful for testing and reproducing exact results.",
    )
    n = IntegerField(
        required=False,
        widget=UnfoldAdminIntegerFieldWidget(attrs={"placeholder": "1"}),
        label="N (Choices)",
        help_text="The number of distinct completions to generate for each prompt.",
    )
    presence_penalty = DecimalField(
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(attrs={"placeholder": "0.0"}),
        label="Presence Penalty",
        help_text="Positive values penalize tokens based on if they have appeared so far, encouraging the model to talk about new topics.",
    )
    frequency_penalty = DecimalField(
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(attrs={"placeholder": "0.0"}),
        label="Frequency Penalty",
        help_text="Positive values penalize tokens based on their existing frequency in the text, decreasing the likelihood of repeating the same lines.",
    )
    stop_sequences = CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(
            attrs={"placeholder": "User:\n<|endoftext|>"}
        ),
        label="Stop Sequences",
        help_text="Enter sequences (one per line). The model will automatically halt generation if it encounters any of these.",
    )
    logit_bias = CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(
            attrs={"placeholder": "100256 = -100\n1234 = 5"}
        ),
        label="Logit Bias (TOML)",
        help_text="Modify the likelihood of specific tokens appearing. Format as TOML mapping token IDs to bias values.",
    )
    provider_params = CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(
            attrs={"placeholder": "top_a = 0.5\nrepetition_penalty = 1.1"}
        ),
        label="Additional Params (TOML)",
        help_text="Any extra sampling parameters specific to your chosen provider, formatted as TOML.",
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
