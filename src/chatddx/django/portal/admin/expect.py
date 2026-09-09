# src/chatddx/django/portal/admin/expect.py
# pyright: basic
from typing import Any

from django.forms import CharField, ModelChoiceField, ModelForm
from django.http import HttpRequest
from unfold.contrib.inlines.admin import NonrelatedTabularInline
from unfold.contrib.inlines.forms import NonrelatedInlineModelFormSet
from unfold.widgets import UnfoldAdminSelectWidget, UnfoldAdminTextareaWidget

from chatddx.django.orm.qs import qs_canon
from chatddx.repo import proxies
from chatddx.repo.branch_models import ExpectBranchModel, ScorerBranchModel
from chatddx.repo.shufflers.expect import dump_expect, load_expects


class ScorerChoiceField(ModelChoiceField):
    def label_from_instance(self, obj: ScorerBranchModel) -> str:
        return obj.name


class ExpectInlineForm(ModelForm):
    payload = CharField(
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 3}),
        label="Expected Payload",
        help_text="The expected output for this Case/Scorer pair.",
    )
    scorer = ScorerChoiceField(
        queryset=ScorerBranchModel.objects.none(),
        required=False,
        widget=UnfoldAdminSelectWidget,
        label="Scorer",
        help_text=(
            "The scorer this expectation is written for (see "
            "ExperimentModel.scorer). Leave blank for the default "
            "expectation of this Case."
        ),
    )

    class Meta:
        model = ExpectBranchModel
        fields: list[str] = []

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            target = self.instance.target
            self.initial.setdefault("payload", target.payload)

            scorer_branch = None
            if target.scorer_id:
                scorer_branch = qs_canon(
                    ScorerBranchModel.objects.filter(target_id=target.scorer_id),
                    self.instance.owner.name,
                ).first()
            self.initial.setdefault("scorer", scorer_branch)


class ExpectInlineFormSet(NonrelatedInlineModelFormSet):
    instance: proxies.Case

    def _dump(self, form: ExpectInlineForm) -> ExpectBranchModel:
        scorer_branch = form.cleaned_data["scorer"]
        scorer = scorer_branch.target if scorer_branch else None

        branch, created = dump_expect(
            case=self.instance.target,  # pyright: ignore
            scorer=scorer,
            payload=form.cleaned_data["payload"],
            owner_name=self.instance.owner.name,
        )

        label = scorer.name if scorer else "default"
        results = getattr(self, "_expect_results", None)
        if results is None:
            results = self._expect_results = []
        results.append((label, created))

        return branch

    def save_new(
        self, form: ExpectInlineForm, commit: bool = True
    ) -> ExpectBranchModel:
        return self._dump(form)

    def save_existing(
        self,
        form: ExpectInlineForm,
        instance: ExpectBranchModel,
        commit: bool = True,
    ) -> ExpectBranchModel:
        return self._dump(form)


class ExpectInline(NonrelatedTabularInline):
    model = ExpectBranchModel
    form = ExpectInlineForm
    formset = ExpectInlineFormSet
    extra = 1
    verbose_name = "Expectation"
    verbose_name_plural = "Expectations"

    def get_form_queryset(self, obj: proxies.Case):
        if obj is None or obj.pk is None:
            return ExpectBranchModel.objects.none()

        return load_expects(obj.target, obj.owner.name)  # pyright: ignore

    def get_formset(
        self, request: HttpRequest, obj: proxies.Case | None = None, **kwargs: Any
    ):
        formset = super().get_formset(request, obj, **kwargs)

        if obj is not None:
            formset.form.base_fields["scorer"].queryset = qs_canon(  # pyright: ignore
                ScorerBranchModel.objects.all(), obj.owner.name
            )

        return formset

    def save_new_instance(
        self, parent: proxies.Case, instance: ExpectBranchModel
    ) -> None:
        raise NotImplementedError
