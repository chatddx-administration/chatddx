# pyright: basic
import json
from collections.abc import AsyncIterator, Iterator
from typing import Any, override

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, OuterRef, Subquery
from django.http import (
    Http404,
    HttpRequest,
    HttpResponseNotAllowed,
    StreamingHttpResponse,
)
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from chatddx.bench.bench import Bench
from chatddx.bench.sending import Handed
from chatddx.django.portal import checking, stacks
from chatddx.django.portal.checking import Checked, Checking, Event
from chatddx.django.portal.models import Stack
from chatddx.django.portal.owners import identity_of
from chatddx.repo.store.branch import readable

Stack._meta.verbose_name = _("stack")
Stack._meta.verbose_name_plural = _("stacks")


class StackAdmin(ModelAdmin):
    list_display_links = ("name_",)
    search_fields = ("name",)
    ordering = ("name",)
    list_per_page = 100

    @override
    def get_list_display(self, request: HttpRequest) -> Any:
        bench = Bench(identity_of(request))

        @admin.display(description=_("LLM"))
        def llm_(stack: Stack) -> str:
            return bench.name_of("llm", stack.trail.llm)

        @admin.display(description=_("Machine"))
        def machine_(stack: Stack) -> str:
            return bench.name_of("machine", stack.trail.machine)

        return ("name_", llm_, machine_, "endpoint_", "slots_", "versions_", "saved_")

    @admin.display(description=_("Name"), ordering="name")
    def name_(self, stack: Stack) -> str:
        return stack.name

    @admin.display(description=_("Endpoint"))
    def endpoint_(self, stack: Stack) -> str:
        return stack.details.get("endpoint") or "—"

    @admin.display(description=_("Slots"))
    def slots_(self, stack: Stack) -> int:
        return stack.details.get("max_jobs") or 1

    @admin.display(description=_("Versions"))
    def versions_(self, stack: Stack) -> int | None:
        return getattr(stack, "versions", None)

    @admin.display(description=_("Saved"), ordering="timestamp")
    def saved_(self, stack: Stack) -> str:
        return date_format(localtime(stack.timestamp), "DATETIME_FORMAT")

    @override
    def get_queryset(self, request: HttpRequest) -> Any:
        bench = Bench(identity_of(request))
        versions = (
            Stack.objects.filter(owner_id=OuterRef("owner_id"), name=OuterRef("name"))
            .values("owner_id", "name")
            .annotate(total=Count("id"))
            .values("total")
        )

        return (
            super()
            .get_queryset(request)
            .filter(pk__in=[row.pk for row in bench.visible("stack")])
            .select_related("owner", "trail__llm", "trail__machine")
            .annotate(versions=Subquery(versions))
        )

    @override
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @override
    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    @override
    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    @override
    def get_urls(self) -> Any:
        return [
            path(
                "<path:object_id>/test/",
                self.admin_site.admin_view(self.test_view),
                name="portal_stack_test",
            ),
            *super().get_urls(),
        ]

    def _row(self, request: HttpRequest, object_id: str) -> Stack:
        if not self.has_view_permission(request):
            raise PermissionDenied

        row = (
            Stack.objects.filter(pk=object_id).select_related("owner", "trail").first()
            if str(object_id).isdigit()
            else None
        )

        if row is None or not readable(row, identity_of(request)):
            raise Http404

        return row

    def _shown(self, request: HttpRequest, object_id: str) -> stacks.Shown:
        llm = request.GET.get("llm", "")
        return stacks.shown(
            self._row(request, object_id),
            identity_of(request),
            int(llm) if llm.isdigit() else None,
        )

    @override
    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: Any = None,
    ) -> Any:
        shown = self._shown(request, object_id)
        test = reverse("admin:portal_stack_test", args=[shown.row.pk])
        context = {
            **self.admin_site.each_context(request),
            "title": shown.row.name,
            "opts": self.opts,
            "original": shown.row,
            "shown": shown,
            "test_url": test + shown.query,
            "checks": checking.CHECKS,
        }

        return TemplateResponse(request, "portal/stack/page.html", context)

    def test_view(self, request: HttpRequest, object_id: str) -> Any:
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        shown = self._shown(request, object_id)
        bench = Bench(identity_of(request))

        return Tested(
            Checking(
                shown.stack,
                shown.llm,
                bench.secret(shown.stack.details.credential),
                checking.TRANSPORT,
            )
        )


class Tested(StreamingHttpResponse):
    def __init__(self, checks: Checking):
        self._checks: Checking = checks
        super().__init__(self._handed_over(), content_type="application/x-ndjson")
        self["Cache-Control"] = "no-cache"
        self["X-Accel-Buffering"] = "no"

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for event in self._checks.events():
            yield self.make_bytes(line_of(event))

    def _handed_over(self) -> Iterator[bytes]:
        with Handed(self._checks.events()) as handed:
            for event in handed:
                yield self.make_bytes(line_of(event))


def line_of(event: Event) -> str:
    match event:
        case Checked():
            drawn = render_to_string("portal/stack/check.html", {"check": event})
            line: dict[str, Any] = {"group": event.group, "html": drawn}
        case _:
            line = {"check": event.key, "stream": event.kind, "text": event.text}

    return json.dumps(line, ensure_ascii=False) + "\n"
