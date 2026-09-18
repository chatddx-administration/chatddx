# pyright: basic

from typing import Any

from django.http import HttpRequest

from chatddx.django.orm.qs import qs_canon
from chatddx.django.portal.branch import BranchModelInlineAdmin
from chatddx.django.portal.forms.expect import ExpectInlineForm, ExpectInlineFormSet
from chatddx.repo.entities.case.django import Case
from chatddx.repo.entities.expect.django import Expect
from chatddx.repo.entities.scorer.django import Scorer, ScorerBranchModel


class ExpectInline(BranchModelInlineAdmin):
    model = Expect
    form = ExpectInlineForm
    formset = ExpectInlineFormSet
    extra = 1
    verbose_name = "Expect"
    verbose_name_plural = "Expects"

    def get_form_queryset(self, obj: Case):
        if obj is None or obj.pk is None:
            return Expect.objects.none()

        return qs_canon(
            Expect.objects.filter(target__cases=obj.target.pk),
            obj.owner.name,
        ).select_related("target")

    def get_formset(self, request: HttpRequest, obj: Case | None = None, **kwargs: Any):
        formset = super().get_formset(request, obj, **kwargs)

        if obj is not None:
            formset.form.base_fields["scorer"].queryset = qs_canon(
                Scorer.objects.all(), obj.owner.name
            )

        return formset
