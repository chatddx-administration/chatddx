# pyright: basic
from typing import Any

from django.contrib import admin, messages
from django.http import HttpRequest

from chatddx.django.portal.admin.base import BranchModelAdmin
from chatddx.django.portal.admin.expect import ExpectInline
from chatddx.django.portal.forms import CaseForm
from chatddx.repo import proxies


@admin.register(proxies.Case)
class CaseAdmin(BranchModelAdmin[proxies.Case]):
    form = CaseForm
    name = "case"
    inlines = [ExpectInline]

    list_display = BranchModelAdmin.list_display + [  # pyright: ignore
        "payload",
        "tags_csv",
    ]

    @admin.display(
        description="Payload",
        ordering="target__payload",
    )
    def payload(self, obj: proxies.Case) -> str:
        return str(obj.target.payload[:40])  # pyright: ignore

    @admin.display(description="Tags")
    def tags_csv(self, obj: proxies.Case) -> str | None:
        return ", ".join(str(tag) for tag in obj.tags.all()) or None

    def sync_extra_relations(self, obj: proxies.Case, form: CaseForm) -> list[str]:
        new_tags = form.cleaned_data.get("tags")
        if new_tags is None:
            return []

        current_ids = set(obj.tags.values_list("pk", flat=True))
        target_ids = {tag.pk for tag in new_tags}

        if current_ids == target_ids:
            return []

        obj.tags.set(target_ids)
        return ["tags"]

    def unchanged_message(self, changed: list[str]) -> str:
        if changed == ["tags"]:
            return "Case payload unchanged, but tags were changed."
        return super().unchanged_message(changed)

    def save_related(
        self,
        request: HttpRequest,
        form: CaseForm,
        formsets: list[Any],
        change: bool,
    ):
        for formset in formsets:
            self.save_formset(request, form, formset, change=change)

    def save_formset(
        self,
        request: HttpRequest,
        form: CaseForm,
        formset: Any,
        change: bool,
    ):
        super().save_formset(request, form, formset, change)

        for label, created in getattr(formset, "_expect_results", []):
            if not created:
                self.message_user(
                    request,
                    f"No changes detected for the '{label}' expectation. "
                    "The current version is up to date.",
                    level=messages.INFO,
                )
