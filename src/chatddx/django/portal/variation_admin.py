# pyright: basic
from typing import Any, ClassVar, override

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.forms import Media
from django.http import (
    Http404,
    HttpRequest,
    HttpResponseNotAllowed,
    HttpResponseRedirect,
)
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import gettext, gettext_lazy as _
from unfold.admin import ModelAdmin

from chatddx.django.portal import records, slices, variations
from chatddx.django.portal.owners import identity_of
from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import EntityName
from chatddx.repo.queries import qs_head
from chatddx.repo.store.branch import commit


class VariationAdmin(ModelAdmin):
    entity: ClassVar[EntityName]
    variation_form: Any
    page_template: ClassVar[str]
    said_template: ClassVar[str]

    list_display_links = ("name_",)
    search_fields = ("name",)
    ordering = ("name",)
    list_per_page = 100
    actions = None

    @admin.display(description=_("Name"), ordering="name")
    def name_(self, row: Any) -> str:
        return row.name

    @admin.display(description=_("Versions"))
    def versions_(self, row: Any) -> int | None:
        return row.version_count

    @admin.display(description=_("Saved"), ordering="timestamp")
    def saved_(self, row: Any) -> str:
        return date_format(localtime(row.timestamp), "DATETIME_FORMAT")

    @override
    def get_queryset(self, request: HttpRequest) -> Any:
        return qs_head(super().get_queryset(request), identity_of(request))

    @override
    def get_urls(self) -> Any:
        return [
            path(
                "check/",
                self.admin_site.admin_view(self.check_view),
                name=self._name("check"),
            ),
            *super().get_urls(),
        ]

    def shown_of(self, owner: str, trail: Any) -> dict[str, Any]:
        return {}

    def _name(self, view: str) -> str:
        return f"{self.opts.app_label}_{self.opts.model_name}_{view}"

    def _url(self, view: str, *args: Any) -> str:
        return reverse(f"admin:{self._name(view)}", args=args)

    def _versions(self, owner: str, name: str) -> list[Any]:
        return list(
            self.model.objects.filter(owner__name=owner, name=name)
            .select_related("owner", "trail")
            .order_by("timestamp", "id")
        )

    def _row(self, request: HttpRequest, object_id: str) -> Any:
        row = (
            self.model.objects.filter(owner__name=identity_of(request), pk=object_id)
            .select_related("owner", "trail")
            .first()
            if str(object_id).isdigit()
            else None
        )

        if row is None:
            raise Http404

        return row

    @override
    def add_view(
        self, request: HttpRequest, form_url: str = "", extra_context: Any = None
    ) -> Any:
        if not self.has_add_permission(request):
            raise PermissionDenied

        owner = identity_of(request)

        if request.method == "POST":
            return self._saved(
                request, owner, self.variation_form(owner, request.POST), []
            )

        return self._page(
            request,
            owner,
            self.variation_form(owner, initial=self.variation_form.BLANK),
            [],
            None,
        )

    @override
    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: Any = None,
    ) -> Any:
        if not self.has_view_permission(request):
            raise PermissionDenied

        owner = identity_of(request)
        row = self._row(request, object_id)
        rows = self._versions(owner, row.name)

        if request.method == "POST":
            if not self.has_change_permission(request):
                raise PermissionDenied

            return self._saved(
                request, owner, self.variation_form(owner, request.POST), rows
            )

        latest = row.pk == rows[-1].pk
        form = (
            self.variation_form(owner, initial=self._initial(row, rows))
            if self.has_change_permission(request) and (latest or "edit" in request.GET)
            else None
        )

        return self._page(request, owner, form, rows, row)

    def _initial(self, row: Any, rows: list[Any]) -> dict[str, Any]:
        number = records.version_of(row, rows).number

        return {
            "edited": row.name,
            "head": rows[-1].pk,
            "since": None if number == len(rows) else number,
            "name": row.name,
            **self.variation_form.initial_of(row.trail),
        }

    def _page(
        self,
        request: HttpRequest,
        owner: str,
        form: Any,
        rows: list[Any],
        row: Any,
    ) -> TemplateResponse:
        version = records.version_of(row, rows) if row is not None else None
        before = rows[version.number - 2] if version and version.number > 1 else None
        edited = rows[-1].name if rows else None
        name, since = _asked(form)
        made = _made(self.variation_form, owner, form) if form is not None else None
        fingerprint = made.fingerprint if made is not None else None
        trail = made if form is not None or row is None else self._trail(row.trail)

        if form is not None:
            for field in form.visible_fields():
                field.field.widget.attrs.update(
                    {
                        "hx-post": self._url("check"),
                        "hx-trigger": "input changed delay:400ms",
                        "hx-target": "#variation-said",
                    }
                )

        context = {
            **self.admin_site.each_context(request),
            "title": edited
            or gettext("Add %(what)s") % {"what": self.opts.verbose_name},
            "opts": self.opts,
            "original": row,
            "version": version,
            "changes": (
                slices.done(self.entity, before.trail, row.trail)
                if before is not None and row is not None
                else []
            ),
            "form": form,
            **(
                self._saying(owner, name, edited, since, fingerprint)
                if form is not None
                else {}
            ),
            "fields": (
                slices.fields_of(self.entity, row.trail)
                if row is not None and form is None
                else []
            ),
            "holds": variations.holds_of(self.entity, owner, rows) if rows else None,
            "said_template": self.said_template,
            "can_change": self.has_change_permission(request),
            "can_delete": self.has_delete_permission(request),
            "media": self.media + (form.media if form is not None else Media()),
            **self.shown_of(owner, trail),
            **self._links(rows, version),
        }

        return TemplateResponse(request, self.page_template, context)

    def _saying(
        self,
        owner: str,
        name: str,
        edited: str | None,
        since: int | None,
        fingerprint: str | None,
    ) -> dict[str, Any]:
        said = variations.said(self.entity, owner, name, edited, since, fingerprint)
        sharers = (
            variations.sharers(self.entity, owner, fingerprint, name, edited)
            if fingerprint
            else []
        )

        return {
            "said": said,
            "taken_url": (
                self._url("change", said.taken.pk) if said.taken is not None else None
            ),
            "sharers": [
                (sharer, self._url("change", sharer.pk) if sharer.own else None)
                for sharer in sharers
            ],
        }

    def _trail(self, trail: Any) -> Any:
        return entity_of(self.entity).trail_out.model_validate(trail)

    def _links(
        self, rows: list[Any], version: records.Version | None
    ) -> dict[str, Any]:
        links: dict[str, Any] = {"changelist_url": self._url("changelist")}

        if version is None:
            return links

        row = rows[version.number - 1]

        return links | {
            "before_url": (
                self._url("change", rows[version.number - 2].pk)
                if version.number > 1
                else None
            ),
            "after_url": (
                self._url("change", rows[version.number].pk)
                if not version.latest
                else None
            ),
            "head_url": self._url("change", rows[-1].pk),
            "edit_url": self._url("change", row.pk) + "?edit=1",
            "delete_url": self._url("delete", row.pk),
        }

    def _saved(
        self, request: HttpRequest, owner: str, form: Any, rows: list[Any]
    ) -> Any:
        since = form.data.get("since", "")
        began = (
            rows[int(since) - 1]
            if since.isdigit() and 0 < int(since) <= len(rows)
            else (rows[-1] if rows else None)
        )

        if not form.is_valid():
            return self._page(request, owner, form, rows, began)

        cleaned = form.cleaned_data
        edited = rows[-1].name if rows else None
        said = variations.said(self.entity, owner, cleaned["name"], edited)

        if said.saving == variations.Saving.TAKEN:
            form.add_error("name", said.line)
            return self._page(request, owner, form, rows, began)

        if said.saving == variations.Saving.NEW and not self.has_add_permission(
            request
        ):
            raise PermissionDenied

        if said.saving == variations.Saving.SAME and rows[-1].pk != cleaned["head"]:
            data = form.data.copy()
            data["head"] = str(rows[-1].pk)
            self.message_user(
                request,
                gettext(
                    "%(name)s has a version %(version)d, saved %(when)s, since you "
                    + "opened it: saving again saves yours as the version after it."
                )
                % {
                    "name": edited,
                    "version": len(rows),
                    "when": date_format(
                        localtime(rows[-1].timestamp), "DATETIME_FORMAT"
                    ),
                },
                messages.WARNING,
            )
            return self._page(
                request, owner, self.variation_form(owner, data), rows, began
            )

        changed = commit(form.trail, form.details)
        head = self._versions(owner, said.name)[-1]
        values = {"name": said.name, "version": said.version, "was": said.version - 1}

        if not changed:
            line = gettext("Nothing changed: %(name)s stays at version %(was)d.")
        elif said.saving == variations.Saving.SAME:
            line = gettext("Saved as version %(version)d of %(name)s.")
        else:
            line = gettext("Saved as a new variation, %(name)s.")

        self.message_user(request, line % values)

        return HttpResponseRedirect(self._url("change", head.pk))

    @override
    def delete_view(
        self, request: HttpRequest, object_id: str, extra_context: Any = None
    ) -> Any:
        if not self.has_delete_permission(request):
            raise PermissionDenied

        owner = identity_of(request)
        row = self._row(request, object_id)
        rows = self._versions(owner, row.name)
        holds = variations.holds_of(self.entity, owner, rows)

        if (
            request.method == "POST"
            and not holds.anything
            and variations.delete_variation(self.entity, owner, row.name)
        ):
            self.message_user(
                request,
                gettext("%(name)s is gone for good.") % {"name": row.name},
            )
            return HttpResponseRedirect(self._url("changelist"))

        context = {
            **self.admin_site.each_context(request),
            "title": gettext("Delete %(name)s") % {"name": row.name},
            "opts": self.opts,
            "original": row,
            "name": row.name,
            "versions": len(rows),
            "holds": holds,
            "back_url": self._url("change", row.pk),
        }

        return TemplateResponse(request, "portal/variation/delete.html", context)

    def check_view(self, request: HttpRequest) -> Any:
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        if not self.has_view_permission(request):
            raise PermissionDenied

        owner = identity_of(request)
        form = self.variation_form(owner, request.POST)
        made = _made(self.variation_form, owner, form)
        fingerprint = made.fingerprint if made is not None else None
        name, since = _asked(form)
        edited = request.POST.get("edited") or None
        context = {
            **self._saying(owner, name, edited, since, fingerprint),
            "oob": True,
            **self.shown_of(owner, made),
        }

        return TemplateResponse(request, self.said_template, context)


def _made(form_class: Any, owner: str, form: Any) -> Any:
    bound = form if form.is_bound else form_class(owner, data=_data(form.initial))
    _ = bound.is_valid()

    return bound.made


def _data(initial: dict[str, Any]) -> dict[str, Any]:
    return {name: "" if value is None else value for name, value in initial.items()}


def _asked(form: Any) -> tuple[str, int | None]:
    if form is None:
        return "", None

    values: Any = form.data if form.is_bound else form.initial
    name = str(values.get("name") or "").strip()
    since = str(values.get("since") or "")

    return name, int(since) if since.isdigit() else None
