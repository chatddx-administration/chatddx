# pyright: basic

from typing import Any

from django.http import HttpRequest

from chatddx.django.orm.qs import qs_canon
from chatddx.django.portal.branch import BranchModelInlineAdmin
from chatddx.django.portal.forms.expect import ExpectInlineForm, ExpectInlineFormSet
from chatddx.repo.entities.case.django import Case
from chatddx.repo.entities.expect.django import Expect
from chatddx.repo.entities.scorer.django import Scorer


class ExpectInline(BranchModelInlineAdmin):
    model = Expect
    form = ExpectInlineForm
    formset = ExpectInlineFormSet
    extra = 1
    verbose_name = "Expect"
    verbose_name_plural = "Expects"

    def get_form_queryset(self, obj: Case):
        """
        The expect branches this version of the case was saved with, in the
        order they were added.

        They are read off the link, not looked up by trail: cases that expect
        the same payload for the same scorer share one content-addressed
        trail, so a trail matches every one of their expectations. Nor are
        they narrowed to canon -- an older version of the case carries the
        version of the expectation it was saved with.
        """
        if obj is None or obj.pk is None:
            return Expect.objects.none()

        return (
            Expect.objects.filter(cases=obj.pk)
            .select_related("target")
            .order_by("timestamp")
        )

    def get_formset(self, request: HttpRequest, obj: Case | None = None, **kwargs: Any):
        formset = super().get_formset(request, obj, **kwargs)

        owner_name = obj.owner.name if obj is not None else request.user.username

        formset.form.base_fields["scorer"].queryset = qs_canon(
            Scorer.objects.all(), owner_name
        )

        return formset
