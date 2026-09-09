# src/chatddx/django/portal/admin/expect.py
# pyright: basic
from typing import Any, final

from django.forms import CharField, ModelForm
from unfold.contrib.inlines.admin import NonrelatedTabularInline
from unfold.contrib.inlines.forms import NonrelatedInlineModelFormSet
from unfold.widgets import UnfoldAdminTextareaWidget, UnfoldAdminTextInputWidget

from chatddx.repo import proxies
from chatddx.repo.branch_models import ExpectBranchModel
from chatddx.repo.shufflers.expect import dump_expect, load_expects


class ExpectInlineForm(ModelForm):
    payload = CharField(
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 3}),
        label="Expected Payload",
        help_text="The expected output for this Case/Scorer pair.",
    )
    scorer = CharField(
        required=False,
        widget=UnfoldAdminTextInputWidget(
            attrs={"placeholder": "e.g., chatddx.experiment.scorers.exact_match"}
        ),
        label="Scorer",
        help_text=(
            "Dotted import path of the scorer function this expectation is "
            "written for (see ExperimentModel.scorer). Leave blank for the "
            "default expectation of this Case."
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
            self.initial.setdefault("scorer", target.scorer)


@final
class ExpectInlineFormSet(NonrelatedInlineModelFormSet):
    instance: proxies.Case

    def _dump(self, form: ExpectInlineForm) -> ExpectBranchModel:
        scorer = form.cleaned_data["scorer"]
        branch, created = dump_expect(
            case=self.instance.target,  # pyright: ignore
            scorer=scorer,
            payload=form.cleaned_data["payload"],
            owner_name=self.instance.owner.name,
        )

        label = scorer or "default"
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


@final
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

    def save_new_instance(
        self, parent: proxies.Case, instance: ExpectBranchModel
    ) -> None:
        raise NotImplementedError
