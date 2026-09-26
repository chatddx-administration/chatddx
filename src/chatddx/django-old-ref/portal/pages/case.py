# pyright: basic
from typing import Any

from django.contrib import admin, messages
from django.http import HttpRequest

from chatddx.django.portal.branch import BranchModelAdmin
from chatddx.django.portal.forms.case import CaseForm
from chatddx.django.portal.forms.expect import ExpectInlineFormSet
from chatddx.django.portal.mixins import SharedMixin
from chatddx.django.portal.pages.expect import ExpectInline
from chatddx.django.portal.request_context import request_contexts
from chatddx.django.portal.utils import truncate_for_list_display
from chatddx.repo.entities.case.django import Case, SharedCase


@admin.register(Case)
class CaseAdmin(BranchModelAdmin[Case]):
    form = CaseForm
    name = "case"
    inlines = (ExpectInline,)

    list_display = list(BranchModelAdmin.list_display) + [
        "payload",
        "tags_csv",
        "collaborators_csv",
    ]

    @admin.display(
        description="Payload",
        ordering="target__payload",
    )
    def payload(self, obj: Case) -> str:
        return truncate_for_list_display(obj.target.payload)  # pyright: ignore

    @admin.display(description="Tags")
    def tags_csv(self, obj: Case) -> str | None:
        return ", ".join(str(tag) for tag in obj.tags.all()) or None

    def save_formset(
        self,
        request: HttpRequest,
        form: CaseForm,
        formset: ExpectInlineFormSet,
        change: Any,
    ):
        super().save_formset(request, form, formset, change)  # pyright: ignore[reportArgumentType]

        for scorer_name, created in formset.outcomes:
            if created:
                continue

            self.message_user(
                request,
                f"No changes detected for the '{scorer_name}' expectation. "
                "The current version is up to date.",
                messages.INFO,
            )

        versioned = any(created for _, created in formset.outcomes)

        if versioned or formset.deleted_objects:
            request_contexts[request].changed.append("expects")


@admin.register(SharedCase)
class SharedCaseAdmin(SharedMixin, CaseAdmin):
    list_display = list(CaseAdmin.list_display) + ["owner"]
