# pyright: basic
import logging
from typing import Any, cast

from django.forms import CharField, ModelChoiceField, ModelForm
from django.forms.formsets import DELETION_FIELD_NAME
from unfold.forms import UnfoldAdminSelectWidget
from unfold.widgets import UnfoldAdminTextareaWidget

from chatddx.core import settings
from chatddx.django.orm.qs import qs_head
from chatddx.django.portal.forms.branch_base import (
    BranchFormSet,
    PydanticValidationError,
)
from chatddx.dx.error_handling import print_pydantic_errors
from chatddx.repo.bundles import presentation_of
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.expect.django import Expect
from chatddx.repo.entities.expect.pydantic import ExpectTrailIn
from chatddx.repo.entities.scorer.django import Scorer
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.pydantic import BaseFormDataIn, BranchDetails
from chatddx.repo.store.branch import commit, get_branch_model

logger = logging.getLogger(__name__)


class ScorerChoiceField(ModelChoiceField):
    def label_from_instance(self, obj: Scorer) -> str:
        return obj.name


class ExpectInlineForm(ModelForm):
    entity_name: EntityName = "expect"

    validated_data: BaseFormDataIn | None = None

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
                scorer_branch = qs_head(
                    Scorer.objects.filter(target_id=target.scorer_id),
                    self.instance.owner.name,
                ).first()
            self.initial.setdefault("scorer", scorer_branch)

    def validate(self, data: dict[str, Any]):
        try:
            validated_data = presentation_of(
                self.entity_name
            ).form_data_in.model_validate(data)
            return validated_data
        except PydanticValidationError as e:
            if settings.MODE == "dev":
                logger.warning("Django Admin form validation failed fyi")
                print_pydantic_errors(e, logger)

            for error in e.errors():
                self.add_error(str(error["loc"][0]), error["msg"])


class ExpectInlineFormSet(BranchFormSet):
    instance: CaseBranchModel
    can_delete: bool

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.outcomes: list[tuple[str, bool]] = []
        self.committed: dict[ExpectInlineForm, Expect] = {}

    def clean(self):
        super().clean()

        for form in self.live_forms():
            if form.errors:
                continue
            form.validated_data = form.validate(self._form_data(form))

    def save(self, commit: bool = True) -> list[Expect]:
        saved = super().save(commit=commit)

        self.instance.expects.set([self._branch(form) for form in self.live_forms()])

        return saved

    def save_new(self, form: ExpectInlineForm, commit: bool = True) -> Expect:
        return self._dump(form, self._branch_name(form))

    def save_existing(
        self,
        form: ExpectInlineForm,
        instance: Expect,
        commit: bool = True,
    ) -> Expect:
        return self._dump(form, instance.name)

    def delete_existing(self, obj: Expect, commit: bool = True) -> None:
        pass

    def live_forms(self) -> list[ExpectInlineForm]:
        forms = cast(
            list[ExpectInlineForm],
            [form for form in self.initial_forms if form.instance.pk]
            + [form for form in self.extra_forms if form.has_changed()],
        )

        return [form for form in forms if not self._is_deleted(form)]

    def _branch(self, form: ExpectInlineForm) -> Expect:
        committed = self.committed.get(form)

        return committed if committed is not None else cast(Expect, form.instance)

    def _is_deleted(self, form: ExpectInlineForm) -> bool:
        return self.can_delete and bool(form.cleaned_data.get(DELETION_FIELD_NAME))

    def _dump(self, form: ExpectInlineForm, branch_name: str) -> Expect:
        data = form.validated_data

        if data is None:
            raise ValueError("form.validated_data is unexpectedly None")

        owner_name = self.instance.owner.name
        schema = ExpectTrailIn.model_validate(data.model_dump())

        created = commit(
            trail=schema,
            branch_details=BranchDetails(
                name=branch_name,
                owner=owner_name,
            ),
        )

        canon = cast(
            Expect,
            get_branch_model(
                entity_name="expect",
                owner_name=owner_name,
                branch_name=branch_name,
                qs=Expect.objects.all(),
            ),
        )

        # consistency check
        assert schema.fingerprint == canon.target.fingerprint

        self.committed[form] = canon
        self.outcomes.append((form.cleaned_data["scorer"].name, created))

        return canon

    def _branch_name(self, form: ExpectInlineForm) -> str:
        return f"{self.instance.name}|{form.cleaned_data['scorer'].name}"

    def _form_data(self, form: ExpectInlineForm) -> dict[str, Any]:
        data = dict(form.cleaned_data)
        scorer_branch = data.pop("scorer", None)

        if scorer_branch is not None:
            data["scorer"] = scorer_branch.target

        return data
