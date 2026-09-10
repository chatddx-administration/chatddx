from typing import Any, final, override

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django.forms import (
    CharField,
    ChoiceField,
)
from unfold.fields import ModelMultipleChoiceField
from unfold.layout import Hr
from unfold.widgets import (
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminSelectMultipleWidget,
    UnfoldAdminTextInputWidget,
)

from chatddx.django.orm.qs import qs_owned_trails
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
        widget=UnfoldAdminTextInputWidget(),
        label="Name",
    )
    template = ChoiceField(
        required=False,
        widget=TemplateSelectWidget(),
        label="Auto-fill from existing tool group",
        help_text="This will overwrite all edited values in the tool group section!",
    )
    tools = ModelMultipleChoiceField(
        queryset=ToolTrailModel.objects.none(),
        widget=UnfoldAdminSelectMultipleWidget(),
        required=False,
        label="Available Tools",
    )
    instructions = CharField(
        required=False,
        widget=UnfoldAdminExpandableTextareaWidget(),
        label="Tool Usage Instructions",
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
