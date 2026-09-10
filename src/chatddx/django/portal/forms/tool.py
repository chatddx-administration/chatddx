from typing import final

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django.forms import (
    CharField,
    ChoiceField,
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
        label="Name",
    )
    template = ChoiceField(
        required=False,
        widget=TemplateSelectWidget(),
        label="Auto-fill from existing case",
        help_text="This will overwrite all edited values!",
    )
    command = CharField(
        max_length=255,
        widget=UnfoldAdminTextInputWidget(),
        label="Command",
    )
    type = ChoiceField(
        choices=ToolChoices.choices,
        widget=UnfoldAdminSelect2Widget(),
        label="Tool Type",
    )
    parameters = CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(),
        label="Parameter Definition",
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
