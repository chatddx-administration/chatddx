# pyright: basic
from crispy_forms.helper import FormHelper, Layout
from crispy_forms.layout import Column, Fieldset, Row
from django import forms
from unfold.layout import Hr
from unfold.widgets import (
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminSelect2Widget,
    UnfoldAdminTextInputWidget,
)

from chatddx.core.choices import ProviderChoices
from chatddx.django.portal.forms.branch_base import BranchForm
from chatddx.django.portal.forms.widgets import TemplateSelectWidget
from chatddx.repo.entities.connection.django import Connection


class ConnectionForm(BranchForm):
    entity_name = "connection"

    class Meta(BranchForm.Meta):
        model = Connection

    name = forms.CharField(
        required=False,
        max_length=255,
        widget=UnfoldAdminTextInputWidget(),
        label="Connection name",
    )
    template = forms.ChoiceField(
        required=False,
        widget=TemplateSelectWidget(),
        label="Auto-fill from existing connection",
        help_text="This will overwrite all edited values in the connection section!",
    )
    model = forms.CharField(
        max_length=255,
        widget=UnfoldAdminTextInputWidget(
            attrs={"placeholder": "e.g. openai/gpt-oss-20b"}
        ),
        label="Model ID",
    )
    provider = forms.ChoiceField(
        choices=ProviderChoices.choices,
        widget=UnfoldAdminSelect2Widget(),
        label="API Provider",
    )
    endpoint = forms.URLField(
        max_length=2048,
        widget=UnfoldAdminTextInputWidget(
            attrs={"placeholder": "e.g. https://api.provider.com/v1/"}
        ),
        label="API Endpoint URL",
    )
    profile = forms.CharField(
        widget=UnfoldAdminExpandableTextareaWidget(),
        required=False,
        label="Provider Parameters",
    )

    helper = FormHelper()
    helper.form_tag = False
    helper.include_media = False

    helper.layout = Layout(
        Fieldset(
            "Connection Settings",
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
                    Row("model"),
                    Row("endpoint"),
                    css_class="w-1/2",
                ),
                Column(
                    Row("provider"),
                    Row("profile"),
                    css_class="w-1/2",
                ),
            ),
            css_class="mb-8",
        )
    )
