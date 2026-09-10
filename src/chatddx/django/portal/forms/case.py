# src/chatddx/django/portal/forms/case.py

from typing import Any, final

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django.forms import (
    CharField,
    ChoiceField,
    ModelMultipleChoiceField,
)
from unfold.layout import Hr
from unfold.widgets import (
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminSelect2MultipleWidget,
    UnfoldAdminTextInputWidget,
)

from chatddx.core.models import IdentityModel, TagModel
from chatddx.django.portal.forms.base import BaseForm
from chatddx.django.portal.forms.widgets import TemplateSelectWidget
from chatddx.repo import proxies
from chatddx.repo.form_data_in import CaseFormDataIn
from chatddx.repo.form_data_out import CaseFormDataOut
from chatddx.repo.shufflers.main import ensure_identity


class TagsField(ModelMultipleChoiceField):
    owner: IdentityModel | None = None

    def clean(self, value: Any) -> list[TagModel]:
        pks: list[str] = []
        names: list[str] = []

        for raw in value or []:
            raw = str(raw).strip()
            if not raw:
                continue
            (pks if raw.isdigit() else names).append(raw)

        tags = list(self.queryset.filter(pk__in=pks))
        tags += [
            TagModel.objects.get_or_create(name=name, owner=self.owner)[0]
            for name in names
        ]
        return tags


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
        label="Name",
    )
    template = ChoiceField(
        required=False,
        widget=TemplateSelectWidget(),
        label="Auto-fill from existing agent",
        help_text="This will overwrite all edited values!",
    )
    payload = CharField(
        widget=UnfoldAdminExpandableTextareaWidget(),
        label="Payload",
    )
    tags = TagsField(
        queryset=TagModel.objects.all(),
        required=False,
        widget=UnfoldAdminSelect2MultipleWidget(
            attrs={"data-tags": "true", "data-placeholder": "Add tags"}
        ),
        label="Tags",
        help_text="Pick existing tags or type a new one to create it.",
    )

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        owner = ensure_identity(self.request.user.username)
        tags_field = self.fields["tags"]
        assert isinstance(tags_field, TagsField)
        tags_field.queryset = TagModel.objects.filter(owner=owner)
        tags_field.owner = owner

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
            Row(
                Column(
                    "tags",
                    css_class="w-full",
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
