# pyright: basic
from django.contrib import admin

from chatddx.django.portal.branch import BranchModelAdmin
from chatddx.django.portal.forms.case import CaseForm
from chatddx.django.portal.mixins import SharedMixin
from chatddx.django.portal.pages.expect import ExpectInline
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


@admin.register(SharedCase)
class SharedCaseAdmin(SharedMixin, CaseAdmin):
    list_display = list(CaseAdmin.list_display) + ["owner"]
