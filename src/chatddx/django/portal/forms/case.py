# src/chatddx/django/repo/admin/forms/case.py

from typing import final

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django.forms import (
    CharField,
    ModelChoiceField,
)
from unfold.layout import Hr
from unfold.widgets import (
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminSelect2Widget,
    UnfoldAdminTextInputWidget,
)

from chatddx.django.portal.forms.base import BaseForm
from chatddx.repo import proxies
from chatddx.repo.form_data_in import CaseFormDataIn
from chatddx.repo.form_data_out import CaseFormDataOut


@final
class CaseForm(BaseForm):
    form_data_in = CaseFormDataIn
    form_data_out = CaseFormDataOut
    bundle_name = "case"

    @final
    class Meta(BaseForm.Meta):
        model = proxies.Case

    name = CharField(
        max_length=255,
        widget=UnfoldAdminTextInputWidget(),
        label="Case Name",
        help_text="Create a new case, or enter an existing name to update it. The latest save becomes the active version.",
    )
    template = ModelChoiceField(
        queryset=proxies.Case.objects.none(),
        required=False,
        empty_label="--- Start from scratch ---",
        widget=UnfoldAdminSelect2Widget(),
        label="Case Template",
        help_text="Optional. Select a pre-configured template to populate the payload below.",
    )
    payload = CharField(
        widget=UnfoldAdminExpandableTextareaWidget(),
        label="Payload",
        help_text="The raw payload content for this case.",
    )

    helper = FormHelper()
    helper.include_media = False
    helper.form_tag = False

    helper.layout = Layout(
        Fieldset(
            "Case Settings",
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
                    "payload",
                    css_class="w-full",
                ),
            ),
        ),
    )
