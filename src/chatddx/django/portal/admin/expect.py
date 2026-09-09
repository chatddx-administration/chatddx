# src/chatddx/django/portal/admin/expect.py
# pyright: basic
from typing import Any, final

from django.forms import CharField, ModelChoiceField, ModelForm
from django.http import HttpRequest
from unfold.contrib.inlines.admin import NonrelatedTabularInline
from unfold.contrib.inlines.forms import NonrelatedInlineModelFormSet
from unfold.widgets import UnfoldAdminSelect2Widget, UnfoldAdminTextareaWidget

from chatddx.repo import proxies
from chatddx.repo.branch_models import ExpectBranchModel, OutputTypeBranchModel
from chatddx.repo.shufflers.expect import dump_expect, load_expects
from chatddx.repo.shufflers.main import qs_canon


class OutputTypeChoiceField(ModelChoiceField):
    def label_from_instance(self, obj: OutputTypeBranchModel) -> str:
        return obj.name or obj.target.fingerprint[:6]


class ExpectInlineForm(ModelForm):
    payload = CharField(
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 3}),
        label="Expected Payload",
        help_text="The expected output for this Case/Output Type pair.",
    )

    class Meta:
        model = ExpectBranchModel
        fields: list[str] = []

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            target = self.instance.target
            self.initial.setdefault("payload", target.payload)

            current = qs_canon(
                OutputTypeBranchModel.objects.filter(target_id=target.output_type_id),
                self.instance.owner.name,
            ).first()
            if current:
                self.initial.setdefault("output_type", current.pk)


@final
class ExpectInlineFormSet(NonrelatedInlineModelFormSet):
    instance: proxies.Case

    def _dump(self, form: ExpectInlineForm) -> ExpectBranchModel:
        output_type = form.cleaned_data["output_type"]
        branch, created = dump_expect(
            case=self.instance.target,  # pyright: ignore
            output_type=output_type.target,
            payload=form.cleaned_data["payload"],
            owner_name=self.instance.owner.name,
        )

        label = output_type.name or output_type.target.fingerprint[:6]
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

    def get_formset(self, request: HttpRequest, obj: Any = None, **kwargs: Any):
        owner_name = obj.owner.name if obj is not None else request.user.username

        output_type_queryset = qs_canon(
            OutputTypeBranchModel.objects.all(),
            owner_name,
        )

        class BoundExpectInlineForm(self.form):
            output_type = OutputTypeChoiceField(
                queryset=output_type_queryset,
                widget=UnfoldAdminSelect2Widget(),
                label="Output Type",
            )

        kwargs["form"] = BoundExpectInlineForm

        return super().get_formset(request, obj, **kwargs)
