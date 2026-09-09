# src/chatddx/django/portal/forms/case.py

from typing import Any, final

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django.forms import (
    CharField,
    ModelChoiceField,
    ModelMultipleChoiceField,
)
from unfold.layout import Hr
from unfold.widgets import (
    UnfoldAdminExpandableTextareaWidget,
    UnfoldAdminSelect2MultipleWidget,
    UnfoldAdminSelect2Widget,
    UnfoldAdminTextInputWidget,
)

from chatddx.core.models import IdentityModel, TagModel
from chatddx.django.portal.forms.base import BaseForm
from chatddx.repo import proxies
from chatddx.repo.form_data_in import CaseFormDataIn
from chatddx.repo.form_data_out import CaseFormDataOut
from chatddx.repo.shufflers.main import ensure_identity


class TagsField(ModelMultipleChoiceField):
    """A tags widget that can create tags on the fly, scoped to one owner.

    The widget below renders as a select2 multi-select with tagging turned
    on (`data-tags`): picking an existing option submits its pk like any
    other `ModelMultipleChoiceField` value, but typing a name with no
    matching tag submits that literal name instead, with no pk behind it.
    Get-or-create it by name -- the same thing `dump_case_tags()` does when
    loading tags from `data/tags.toml` -- rather than rejecting it as an
    invalid choice.

    Tags are owner-scoped (see TagModel), so both the suggestions offered
    (`queryset`, set by `CaseForm.__init__`) and any tag created here are
    confined to `owner` -- one owner's tags never show up as suggestions
    for, or get silently reused by, another.
    """

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
