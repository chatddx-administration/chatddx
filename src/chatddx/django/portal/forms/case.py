# pyright: basic

from typing import Any

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

from chatddx.core.models import TagModel
from chatddx.core.utils import ensure_identity
from chatddx.django.portal.forms.branch_base import BranchForm
from chatddx.django.portal.forms.widgets import TemplateSelectWidget
from chatddx.repo.entities.case.django import Case


class TagsField(ModelMultipleChoiceField):
    def clean(self, value: Any) -> list[TagModel | str]:
        """
        Existing tags come in as pks and are looked up in the queryset, which
        is the owner's tags for this entity and nothing else. A typed one
        comes in as its name and stays a name: tags are created where every
        other branch relation is, when the branch is saved.
        """
        pks: list[str] = []
        names: list[str] = []

        for raw in value or []:
            raw = str(raw).strip()
            if not raw:
                continue
            (pks if raw.isdigit() else names).append(raw)

        return list(self.queryset.filter(pk__in=pks)) + names


class CaseForm(BranchForm):
    entity_name = "case"

    class Meta(BranchForm.Meta):
        model = Case

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

        # a tag is the owner's label for one kind of entity, so cases are only
        # ever offered, and only ever keep, the case tags of their owner
        tags_field.queryset = TagModel.objects.filter(
            owner=owner,
            entity=self.entity_name,
        )

    def get_initial(self, instance: Case) -> dict[str, Any]:
        # tags live on the branch, not in its form data, and the widget wants
        # them as the pks of its own choices
        return super().get_initial(instance) | {
            "tags": list(instance.tags.values_list("pk", flat=True)),
        }

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
