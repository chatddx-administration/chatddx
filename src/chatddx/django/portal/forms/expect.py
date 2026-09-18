# pyright: basic
import logging
from typing import Any

from django.forms import CharField, ModelChoiceField, ModelForm
from unfold.forms import UnfoldAdminSelectWidget
from unfold.widgets import UnfoldAdminTextareaWidget

from chatddx.core import settings
from chatddx.django.orm.qs import qs_canon
from chatddx.django.portal.forms.branch_base import (
    BranchFormSet,
    PydanticValidationError,
)
from chatddx.dx.error_handling import print_pydantic_errors
from chatddx.repo.bundles import bundle_of
from chatddx.repo.entities.expect.django import Expect
from chatddx.repo.entities.scorer.django import Scorer
from chatddx.repo.shufflers.branch import commit

logger = logging.getLogger(__name__)


class ScorerChoiceField(ModelChoiceField):
    def label_from_instance(self, obj: Scorer) -> str:
        return obj.name


class ExpectInlineForm(ModelForm):
    entity_name = "expect"

    payload = CharField(
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 1}),
        label="Expected Payload",
    )
    scorer = ScorerChoiceField(
        queryset=Scorer.objects.none(),
        required=False,
        widget=UnfoldAdminSelectWidget,
        label="Scorer",
    )

    class Meta:
        model = Expect
        fields = ()

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            target = self.instance.target
            self.initial.setdefault("payload", target.payload)

            scorer_branch = None
            if target.scorer_id:
                scorer_branch = qs_canon(
                    Scorer.objects.filter(target_id=target.scorer_id),
                    self.instance.owner.name,
                ).first()
            self.initial.setdefault("scorer", scorer_branch)

    def validate(self, data: dict[str, Any]):
        try:
            validated_data = bundle_of(self.entity_name).form_data_in.model_validate(
                data
            )
            return validated_data
        except PydanticValidationError as e:
            if settings.MODE == "dev":
                logger.warning("Django Admin form validation failed fyi")
                print_pydantic_errors(e, logger)

            for error in e.errors():
                self.add_error(str(error["loc"][0]), error["msg"])


class ExpectInlineFormSet(BranchFormSet):
    def clean(self):
        super().clean()
        raise

    def _dump(self, form: ExpectInlineForm) -> Expect:
        form.validate(form.cleaned_data)
        return
        raise
        scorer_branch = form.cleaned_data["scorer"]

        created = commit(
            BranchD,
            case=self.instance.target,
            scorer=scorer_branch.target,
            payload=form.cleaned_data["payload"],
            owner_name=self.instance.owner.name,
        )

        label = scorer.name if scorer else "default"
        results = getattr(self, "_expect_results", None)
        if results is None:
            results = self._expect_results = []
        results.append((label, created))

        return branch

    def save_new(self, form: ExpectInlineForm, commit: bool = True) -> Expect:
        return self._dump(form)

    def save_existing(
        self,
        form: ExpectInlineForm,
        instance: Expect,
        commit: bool = True,
    ) -> Expect:
        return self._dump(form)
