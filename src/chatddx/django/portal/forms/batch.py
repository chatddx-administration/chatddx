# pyright: basic
from typing import Any

from django.forms import (
    BooleanField,
    ModelChoiceField,
    ModelForm,
    ModelMultipleChoiceField,
)
from unfold.widgets import (
    UnfoldAdminSelect2MultipleWidget,
    UnfoldAdminSelectMultipleWidget,
    UnfoldAdminSelectWidget,
    UnfoldBooleanWidget,
)

from chatddx.core.models import TagModel
from chatddx.django.portal.qs import qs_head, qs_owned_trails
from chatddx.history.proxies import Batch
from chatddx.repo.entities.agent.django import AgentTrailModel
from chatddx.repo.entities.scorer.django import Scorer
from chatddx.repo.entity_names import EntityName

CASE_ENTITY: EntityName = "case"

NO_SCORERS_HELP = (
    "Leave empty to run every scorer each case carries. "
    "Cases without any of the chosen scorers are left out of the batch."
)


class BatchForm(ModelForm):
    class Meta:
        model = Batch
        fields = ("agent", "case_tags", "scorers")

    agent = ModelChoiceField(
        queryset=AgentTrailModel.objects.none(),
        widget=UnfoldAdminSelectWidget,
        label="Agent",
    )
    case_tags = ModelMultipleChoiceField(
        queryset=TagModel.objects.none(),
        widget=UnfoldAdminSelect2MultipleWidget(
            attrs={"data-placeholder": "Pick case tags"}
        ),
        label="Case tags",
    )
    scorers = ModelMultipleChoiceField(
        queryset=Scorer.objects.none(),
        required=False,
        widget=UnfoldAdminSelectMultipleWidget,
        label="Scorers",
        help_text=NO_SCORERS_HELP,
    )
    queue_immediately = BooleanField(
        initial=True,
        required=False,
        widget=UnfoldBooleanWidget,
        label="Queue immediately",
    )

    def __init__(self, *args: Any, **kwargs: Any):
        self.request = kwargs.pop("request")

        super().__init__(*args, **kwargs)

        owner_name = self.request.user.username

        self._choices("agent").queryset = qs_owned_trails(
            AgentTrailModel.objects.all(),
            owner_name,
        )
        self._choices("case_tags").queryset = TagModel.objects.filter(
            owner__name=owner_name,
            entity=CASE_ENTITY,
        ).order_by("name")
        self._choices("scorers").queryset = qs_head(
            Scorer.objects.all(),
            owner_name,
        ).order_by("name")

    def _choices(self, name: str) -> ModelChoiceField:
        field = self.fields[name]

        assert isinstance(field, ModelChoiceField)

        return field
