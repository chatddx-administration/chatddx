# pyright: basic
from typing import Any, override

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest
from django.template.response import TemplateResponse
from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from chatddx.bench.bench import Bench
from chatddx.bench.cell import SLICES
from chatddx.django.portal import configurations, records, slices
from chatddx.django.portal.models import Configuration
from chatddx.django.portal.owners import identity_of
from chatddx.repo.queries import qs_head

Configuration._meta.verbose_name = _("configuration")
Configuration._meta.verbose_name_plural = _("configurations")


class ConfigurationAdmin(ModelAdmin):
    list_display_links = ("name_",)
    search_fields = ("name",)
    ordering = ("name",)
    list_per_page = 100

    @override
    def get_list_display(self, request: HttpRequest) -> Any:
        bench = Bench(identity_of(request))

        def column(entity: Any) -> Any:
            @admin.display(description=slices.LABELS[entity])
            def variation(configuration: Configuration) -> str:
                return bench.name_of(entity, getattr(configuration.trail, entity))

            return variation

        return ("name_", *(column(entity) for entity in SLICES), "versions_", "saved_")

    @admin.display(description=_("Name"), ordering="name")
    def name_(self, configuration: Configuration) -> str:
        return configuration.name

    @admin.display(description=_("Versions"))
    def versions_(self, configuration: Configuration) -> int | None:
        return configuration.version_count

    @admin.display(description=_("Saved"), ordering="timestamp")
    def saved_(self, configuration: Configuration) -> str:
        return date_format(localtime(configuration.timestamp), "DATETIME_FORMAT")

    @override
    def get_queryset(self, request: HttpRequest) -> Any:
        return qs_head(
            super().get_queryset(request), identity_of(request)
        ).select_related(*(f"trail__{entity}" for entity in SLICES))

    @override
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @override
    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    @override
    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def _row(self, request: HttpRequest, object_id: str) -> Configuration:
        if not self.has_view_permission(request):
            raise PermissionDenied

        row = (
            Configuration.objects.filter(pk=object_id)
            .select_related("owner", "trail")
            .first()
            if str(object_id).isdigit()
            else None
        )

        if row is None or not records.readable(row, identity_of(request)):
            raise Http404

        return row

    @override
    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: Any = None,
    ) -> Any:
        identity = identity_of(request)
        row = self._row(request, object_id)
        shown = configurations.shown(
            row, identity, configurations.pinned(identity, request.GET)
        )
        context = {
            **self.admin_site.each_context(request),
            "title": shown.label,
            "opts": self.opts,
            "original": row,
            "shown": shown,
        }

        return TemplateResponse(request, "portal/configuration/page.html", context)
