# pyright: basic

import uuid
from typing import Any, override

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.formats import date_format
from django.utils.html import escape
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from chatddx.django.portal import runs
from chatddx.django.portal.models import Run
from chatddx.django.portal.owners import identity_of
from chatddx.django.portal.status import value_of

Run._meta.verbose_name = _("run")
Run._meta.verbose_name_plural = _("runs")


class RunAdmin(ModelAdmin):
    list_display = ("run_", "when_", "trial_", "outcome_", "scores_")
    list_display_links = ("run_",)
    search_fields = ("conversation__description",)
    ordering = ("-timestamp", "-pk")
    list_per_page = 50

    @admin.display(description=_("Run"))
    def run_(self, run: Run) -> str:
        return str(run.uuid)[:8]

    @admin.display(description=_("When"), ordering="timestamp")
    def when_(self, run: Run) -> str:
        return date_format(localtime(run.timestamp), "DATETIME_FORMAT")

    @admin.display(description=_("Trial"))
    def trial_(self, run: Run) -> str:
        return runs.description_of(run)

    @admin.display(description=_("Outcome"))
    def outcome_(self, run: Run) -> str:
        outcome, _trouble = runs.outcome_of(run)
        return outcome

    @admin.display(description=_("Scores"))
    def scores_(self, run: Run) -> str:
        latest: dict[str, str] = {}

        for score in sorted(run.scores.all(), key=lambda score: score.pk):
            if score.owner_id == run.owner_id:
                latest[score.scorer_name] = value_of(score.value)

        return " · ".join(f"{name} {value}" for name, value in sorted(latest.items()))

    @override
    def get_queryset(self, request: HttpRequest) -> Any:
        return (
            super()
            .get_queryset(request)
            .filter(owner__name=identity_of(request))
            .select_related("conversation")
            .prefetch_related("scores")
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
                "<path:object_id>/exchange/<int:number>/<str:which>/",
                self.admin_site.admin_view(self.exchange_view),
                name="portal_run_exchange",
            ),
            *super().get_urls(),
        ]

    def _run(self, request: HttpRequest, object_id: str) -> Run:
        if not self.has_view_permission(request):
            raise PermissionDenied

        mine = Run.objects.filter(owner__name=identity_of(request)).select_related(
            "owner",
            "trial",
            "conversation",
            "client",
            "stack_branch",
            "llm_branch",
        )

        try:
            found = mine.filter(uuid=uuid.UUID(object_id)).first()
        except ValueError:
            found = mine.filter(pk=object_id).first() if object_id.isdigit() else None

        if found is None:
            raise Http404

        return found

    @override
    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: Any = None,
    ) -> Any:
        run = self._run(request, object_id)
        context = {
            **self.admin_site.each_context(request),
            "title": runs.description_of(run),
            "opts": self.opts,
            "original": run,
            "shown": runs.shown(run),
        }

        return TemplateResponse(request, "portal/run/page.html", context)

    def exchange_view(
        self, request: HttpRequest, object_id: str, number: int, which: str
    ) -> HttpResponse:
        if which not in ("request", "response"):
            raise Http404

        body = runs.exchange_of(self._run(request, object_id), number, which)

        if body is None:
            raise Http404

        return HttpResponse(escape(body))
