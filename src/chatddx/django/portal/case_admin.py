# pyright: basic
"""
The cases' pages: the owner's cases, to go through one by one; a case's own
page, its timeline to step through, where a save makes a new version of
whichever case its name names, asking first where that is another; deleting
a version, or cases, gone where nothing reads them and out of sight where
something does; and, as a page is typed, what saving it would do.
"""

from copy import copy
from typing import Any, override

from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter, options
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.core.exceptions import PermissionDenied
from django.forms import Media
from django.http import (
    Http404,
    HttpRequest,
    HttpResponseNotAllowed,
    HttpResponseRedirect,
    QueryDict,
)
from django.middleware.csrf import get_token
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.formats import date_format
from django.utils.html import format_html, format_html_join
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import localtime
from django.utils.translation import gettext, gettext_lazy as _, ngettext
from unfold.admin import ModelAdmin

from chatddx.bench.bench import Bench
from chatddx.django.portal import cases
from chatddx.django.portal.forms import CaseForm, initial_of
from chatddx.django.portal.models import Case
from chatddx.django.portal.owners import identity_of
from chatddx.repo.queries import qs_head
from chatddx.repo.store.branch import commit

# what the confirmation of a save onto another case posts: the head it showed
ONTO = "_onto"
# what its Back posts: the form again, as it was
BACK = "_back"

# what the portal calls a case, for the model holds no words of the portal's
Case._meta.verbose_name = _("case")
Case._meta.verbose_name_plural = _("cases")


class TagFilter(SimpleListFilter):
    title = _("tag")
    parameter_name = "tag"

    @override
    def lookups(self, request: HttpRequest, model_admin: Any) -> Any:
        own = Bench(identity_of(request), own=("case",))
        return [(tag, tag) for tag in own.tags("case")]

    @override
    def queryset(self, request: HttpRequest, queryset: Any) -> Any:
        tag = self.value()
        return queryset.filter(tags__name=tag) if tag else queryset


class LanguageFilter(SimpleListFilter):
    title = _("language")
    parameter_name = "language"

    @override
    def lookups(self, request: HttpRequest, model_admin: Any) -> Any:
        return [("en", _("English")), ("sv", _("Swedish")), ("none", _("none"))]

    @override
    def queryset(self, request: HttpRequest, queryset: Any) -> Any:
        match self.value():
            case None:
                return queryset
            case "none":
                return queryset.filter(details__language=None)
            case language:
                return queryset.filter(details__language=language)


class TargetsFilter(SimpleListFilter):
    """The cases still wanting something of their targets: the clinicians' to-do list."""

    title = _("targets")
    parameter_name = "wanting"

    @override
    def lookups(self, request: HttpRequest, model_admin: Any) -> Any:
        return [
            ("text", _("wanting a text")),
            ("pattern", _("wanting a pattern")),
            ("unread", _("with a pattern that doesn't parse")),
        ]

    @override
    def queryset(self, request: HttpRequest, queryset: Any) -> Any:
        wanted = self.value()

        if wanted not in ("text", "pattern", "unread"):
            return queryset

        return queryset.filter(
            pk__in=[
                case.pk for case in queryset if cases.needs_of(case.details)[wanted]
            ]
        )


class CaseAdmin(ModelAdmin):
    list_display = ("name_", "language_", "wanting_", "tags_", "versions_", "saved_")
    list_display_links = ("name_",)
    list_filter = (TagFilter, LanguageFilter, TargetsFilter)
    search_fields = ("name", "trail__vignette")
    ordering = ("name",)
    list_per_page = 100
    actions = ("delete_cases",)

    @admin.display(description=_("Name"), ordering="name")
    def name_(self, case: Case) -> str:
        return case.name

    @admin.display(description=_("Language"))
    def language_(self, case: Case) -> str:
        return case.details.get("language") or "—"

    @admin.display(description=_("Still wanting"))
    def wanting_(self, case: Case) -> Any:
        needs = cases.needs_of(case.details)
        said = [
            (label, ", ".join(str(cases.KINDS[kind]) for kind in needs[need]), style)
            for need, label, style in (
                ("text", gettext("text"), "portal-missing"),
                ("pattern", gettext("pattern"), "portal-missing"),
                ("unread", gettext("doesn't parse"), "portal-refused"),
            )
            if needs[need]
        ]

        if not said:
            return "—"

        return format_html_join(
            format_html("{}", " · "),
            '<span class="{2}">{0}: {1}</span>',
            said,
        )

    @admin.display(description=_("Tags"))
    def tags_(self, case: Case) -> str:
        return " ".join(sorted(tag.name for tag in case.tags.all())) or "—"

    @admin.display(description=_("Versions"))
    def versions_(self, case: Case) -> int | None:
        return case.version_count

    @admin.display(description=_("Saved"), ordering="timestamp")
    def saved_(self, case: Case) -> str:
        return date_format(localtime(case.timestamp), "DATETIME_FORMAT")

    @override
    def get_queryset(self, request: HttpRequest) -> Any:
        """The head of each of the owner's cases, the deleted aside."""
        return (
            qs_head(super().get_queryset(request), identity_of(request))
            .exclude(details__contains={"deleted": True})
            .prefetch_related("tags")
        )

    @override
    def get_actions(
        self,
        request: HttpRequest,
        action_location: Any = options.ActionLocation.CHANGE_LIST,  # pyright: ignore[reportAttributeAccessIssue]
    ) -> Any:
        # the admin's since Django 6.1, which the stubs don't know yet
        actions = super().get_actions(request, action_location)  # pyright: ignore[reportCallIssue]
        # deleting cases is the portal's own: gone, or out of sight
        _ = actions.pop("delete_selected", None)
        return actions

    @admin.action(description=_("Delete the cases ticked"), permissions=["delete"])
    def delete_cases(self, request: HttpRequest, queryset: Any) -> Any:
        """
        The cases ticked deleted, once their owner has seen what that does:
        each gone where nothing reads it, and out of sight where something does.
        """
        owner = identity_of(request)
        names = sorted(queryset.values_list("name", flat=True))

        if request.POST.get("post") == "yes":
            deleted = [cases.delete_case(owner, name) for name in names]
            gone = deleted.count(cases.Deleted.GONE)
            self.message_user(
                request,
                gettext(
                    "%(gone)d gone for good, nothing having read them; %(hidden)d "
                    + "out of sight, kept for the runs that read them."
                )
                % {"gone": gone, "hidden": len(deleted) - gone},
            )
            return None

        context = {
            **self.admin_site.each_context(request),
            "title": _("Delete cases"),
            "opts": self.opts,
            "held": [
                (name, cases.case_held(cases.versions_of(owner, name)))
                for name in names
            ],
            "queryset": queryset,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "action": "delete_cases",
        }

        return TemplateResponse(request, "portal/case/delete_cases.html", context)

    @override
    def get_urls(self) -> Any:
        # before the admin's own, whose object_id would take these for one
        return [
            path(
                "check/",
                self.admin_site.admin_view(self.check_view),
                name="portal_case_check",
            ),
            path(
                "<path:object_id>/untag/",
                self.admin_site.admin_view(self.untag_view),
                name="portal_case_untag",
            ),
            path(
                "<path:object_id>/score/",
                self.admin_site.admin_view(self.score_view),
                name="portal_case_score",
            ),
            path(
                "<path:object_id>/restore/",
                self.admin_site.admin_view(self.restore_view),
                name="portal_case_restore",
            ),
            *super().get_urls(),
        ]

    def _row(self, request: HttpRequest, object_id: str) -> Case:
        """A version of one of the owner's cases, or none to be found."""
        row = (
            Case.objects.filter(owner__name=identity_of(request), pk=object_id)
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
        """A blank case, or a name to start one under."""
        if not self.has_add_permission(request):
            raise PermissionDenied

        owner = identity_of(request)

        if request.method == "POST":
            return self._saved(request, owner, CaseForm(owner, request.POST), None)

        form = CaseForm(owner, initial={"name": request.GET.get("name", "")})

        return self._page(request, owner, form, None, None)

    @override
    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: Any = None,
    ) -> Any:
        """
        A version of the case, in its timeline: the head to edit, and an
        earlier one to read, or to edit from.
        """
        if not self.has_view_permission(request):
            raise PermissionDenied

        owner = identity_of(request)
        row = self._row(request, object_id)
        timeline = cases.Timeline.of(row)
        version = timeline.version_of(row)

        if request.method == "POST":
            if not self.has_change_permission(request):
                raise PermissionDenied

            return self._saved(request, owner, CaseForm(owner, request.POST), timeline)

        editing = (
            self.has_change_permission(request)
            and not timeline.head.deleted
            and (version.is_head or "edit" in request.GET)
        )
        form = (
            CaseForm(owner, initial=initial_of(version, timeline)) if editing else None
        )

        return self._page(request, owner, form, timeline, version)

    def _page(
        self,
        request: HttpRequest,
        owner: str,
        form: CaseForm | None,
        timeline: cases.Timeline | None,
        version: cases.Version | None,
    ) -> TemplateResponse:
        """A case's page: a version in its timeline, and the form, where it is edited."""
        name, vignette, since = _asked(form)
        edited = timeline.name if timeline else None
        shown = version or (timeline.head if timeline else None)
        vignette = cases.vignette_of(owner, vignette) if vignette.strip() else ""

        # what saving would do, said again as the name and the vignette are typed
        for field, delay in (("name", 300), ("vignette", 800)):
            if form is not None:
                form.fields[field].widget.attrs.update(
                    {
                        "hx-post": reverse("admin:portal_case_check"),
                        "hx-trigger": f"input changed delay:{delay}ms",
                        "hx-target": "#case-said",
                    }
                )

        context = {
            **self.admin_site.each_context(request),
            "title": timeline.name if timeline else _("Add case"),
            "opts": self.opts,
            # what the header names: the case, where the page is of one
            "original": shown.row.as_proxy(Case) if shown else None,
            "timeline": timeline,
            "version": version,
            "before": timeline.before(version) if timeline and version else None,
            "after": timeline.after(version) if timeline and version else None,
            "changes": (
                cases.changes(timeline.before(version), version)
                if timeline and version
                else []
            ),
            "form": form,
            "said": cases.said(owner, name, edited, since) if form else None,
            "sharers": (
                cases.sharers(owner, vignette, name.strip(), edited) if vignette else []
            ),
            "vignette_changed": bool(shown and vignette and vignette != shown.vignette),
            "runs": (
                cases.runs_of(
                    owner, shown.row.trail_id, {row.trail_id for row in timeline.rows}
                )
                if timeline and shown
                else None
            ),
            "next": request.get_full_path(),
            "can_change": self.has_change_permission(request),
            "can_delete": self.has_delete_permission(request),
            "media": self.media + (form.media if form else Media()),
            **self._links(request, timeline, version),
        }

        return TemplateResponse(request, "portal/case/change_form.html", context)

    def _kept(self, request: HttpRequest, url: str) -> str:
        """`url`, keeping the filters of the list the page came from."""
        return add_preserved_filters(
            {
                "preserved_filters": self.get_preserved_filters(request),
                "opts": self.opts,
            },
            url,
        )

    def _links(
        self,
        request: HttpRequest,
        timeline: cases.Timeline | None,
        version: cases.Version | None,
    ) -> dict[str, Any]:
        """
        Where the page leads: the list, the versions before and after, the
        cases before and after in the list it came from, filtered as it was.
        """

        def change(row: Any, *query: str) -> str:
            url = reverse("admin:portal_case_change", args=[row.pk])
            return self._kept(request, f"{url}?{'&'.join(query)}" if query else url)

        links: dict[str, Any] = {
            "changelist_url": self._kept(
                request, reverse("admin:portal_case_changelist")
            )
        }

        if timeline is None or version is None:
            return links

        before, after = timeline.before(version), timeline.after(version)
        listed = self._listed(request)
        names = [name for _pk, name in listed]
        at = names.index(timeline.name) if timeline.name in names else None
        previous = listed[at - 1] if at else None
        following = listed[at + 1] if at is not None and at + 1 < len(listed) else None

        return links | {
            "before_url": change(before.row) if before else None,
            "after_url": change(after.row) if after else None,
            "head_url": change(timeline.head.row),
            "edit_url": change(version.row, "edit=1"),
            "delete_url": self._kept(
                request, reverse("admin:portal_case_delete", args=[version.row.pk])
            ),
            "previous_case": previous and (previous[1], change(Case(pk=previous[0]))),
            "next_case": following and (following[1], change(Case(pk=following[0]))),
        }

    def _listed(self, request: HttpRequest) -> list[tuple[int, str]]:
        """The cases of the list the page came from, in its order, filtered as it was."""
        listed = copy(request)
        listed.GET = QueryDict(request.GET.get("_changelist_filters", ""))

        try:
            changelist = self.get_changelist_instance(listed)
        except IncorrectLookupParameters:
            return []

        return list(changelist.queryset.values_list("pk", "name"))

    def _saved(
        self,
        request: HttpRequest,
        owner: str,
        form: CaseForm,
        timeline: cases.Timeline | None,
    ) -> Any:
        """
        The page's case saved as a new version of whichever case its name
        names, once nothing stands in the way: the page's own case having
        moved on since it was opened, or another case's content it replaces.
        """
        began = _began(timeline, form.data.get("since", ""))

        if BACK in request.POST or not form.is_valid():
            return self._page(request, owner, form, timeline, began)

        cleaned = form.cleaned_data
        edited = timeline.name if timeline else None
        said = cases.said(owner, cleaned["name"], edited, cleaned["since"])

        # a new case, from whichever page, is an add
        if said.saving == cases.Saving.NEW and not self.has_add_permission(request):
            raise PermissionDenied

        if timeline is not None and timeline.head.row.pk != cleaned["head"]:
            data = form.data.copy()
            data["head"] = str(timeline.head.row.pk)
            self.message_user(
                request,
                gettext(
                    "%(name)s has a version %(version)d, saved %(when)s, since you "
                    + "opened it: saving again saves yours as the version after it."
                )
                % {
                    "name": timeline.name,
                    "version": timeline.head.number,
                    "when": date_format(
                        localtime(timeline.head.row.timestamp), "DATETIME_FORMAT"
                    ),
                },
                messages.WARNING,
            )
            return self._page(request, owner, CaseForm(owner, data), timeline, began)

        if said.onto is not None and request.POST.get(ONTO) != str(said.onto.pk):
            return self._confirmation(request, form, said)

        saved_to = said.onto or (
            timeline.head.row if timeline and edited == said.name else None
        )
        tags_before = (
            sorted(tag.name for tag in saved_to.tags.all()) if saved_to else None
        )
        changed = commit(form.trail, form.details)
        head = cases.versions_of(owner, said.name)[-1]
        self.message_user(
            request, _said_of(said, changed, tags_before, cleaned["tags"])
        )

        return HttpResponseRedirect(
            self._kept(request, reverse("admin:portal_case_change", args=[head.pk]))
        )

    def _confirmation(
        self, request: HttpRequest, form: CaseForm, said: cases.Said
    ) -> TemplateResponse:
        """A save onto another case, shown before it is done: its head beside the page."""
        assert said.onto is not None
        theirs = cases.Timeline.of(said.onto).head
        ours = form.draft
        context = {
            **self.admin_site.each_context(request),
            "title": gettext("Save onto %(name)s") % {"name": said.name},
            "opts": self.opts,
            "said": said,
            "theirs": theirs,
            "ours": ours,
            "changes": cases.changes(theirs, ours),
            "asked": [
                (name, value)
                for name, values in request.POST.lists()
                if name not in ("csrfmiddlewaretoken", ONTO, BACK)
                for value in values
            ],
            "onto": ONTO,
            "onto_pk": said.onto.pk,
            "back": BACK,
            "action_url": request.get_full_path(),
        }

        return TemplateResponse(request, "portal/case/confirmation.html", context)

    @override
    def delete_view(
        self, request: HttpRequest, object_id: str, extra_context: Any = None
    ) -> Any:
        """
        A version deleted, once its owner has seen what that does: where it
        is the case's only one, the case with it.
        """
        if not self.has_delete_permission(request):
            raise PermissionDenied

        owner = identity_of(request)
        row = self._row(request, object_id)
        timeline = cases.Timeline.of(row)
        version = timeline.version_of(row)
        only = len(timeline.rows) == 1
        held = cases.case_held(timeline.rows) if only else cases.version_held(row)

        if request.method == "POST" and (only or not held):
            if only:
                return self._case_deleted(request, owner, timeline.name)

            _ = row.delete()
            head = cases.versions_of(owner, timeline.name)[-1]
            said = gettext("Version %(number)d of %(name)s is deleted.") % {
                "number": version.number,
                "name": timeline.name,
            }

            if version.is_head:
                said += " " + gettext("Version %(number)d is its head again.") % {
                    "number": version.number - 1
                }

            self.message_user(request, said)

            return HttpResponseRedirect(
                self._kept(request, reverse("admin:portal_case_change", args=[head.pk]))
            )

        context = {
            **self.admin_site.each_context(request),
            "title": gettext("Delete version %(number)d of %(name)s")
            % {"number": version.number, "name": timeline.name},
            "opts": self.opts,
            "timeline": timeline,
            "version": version,
            "only": only,
            "held": held,
            "can": only or not held,
            "back_url": self._kept(
                request, reverse("admin:portal_case_change", args=[row.pk])
            ),
        }

        return TemplateResponse(request, "portal/case/delete.html", context)

    def _case_deleted(self, request: HttpRequest, owner: str, name: str) -> Any:
        deleted = cases.delete_case(owner, name)
        changelist = HttpResponseRedirect(
            self._kept(request, reverse("admin:portal_case_changelist"))
        )

        if deleted == cases.Deleted.GONE:
            self.message_user(
                request,
                gettext("%(name)s is gone for good: nothing had read it.")
                % {"name": name},
            )
            return changelist

        head = cases.versions_of(owner, name)[-1]
        self.message_user(
            request,
            format_html(
                '{} <form class="inline" method="post" action="{}">'
                + '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
                + '<button class="font-semibold underline" type="submit">{}</button>'
                + "</form>",
                gettext(
                    "%(name)s is out of sight, kept for the runs that read it: they "
                    + "keep its name and targets."
                )
                % {"name": name},
                reverse("admin:portal_case_restore", args=[head.pk]),
                get_token(request),
                gettext("Undo"),
            ),
        )

        return changelist

    def restore_view(self, request: HttpRequest, object_id: str) -> Any:
        """A deleted case brought back, as its Undo asks."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        if not self.has_change_permission(request):
            raise PermissionDenied

        owner = identity_of(request)
        row = self._row(request, object_id)
        cases.restore(owner, row.name)
        head = cases.versions_of(owner, row.name)[-1]
        self.message_user(request, gettext("%(name)s is back.") % {"name": row.name})

        return HttpResponseRedirect(reverse("admin:portal_case_change", args=[head.pk]))

    def untag_view(self, request: HttpRequest, object_id: str) -> Any:
        """Another case's tags taken off, as a page sharing its vignette offers."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        if not self.has_change_permission(request):
            raise PermissionDenied

        row = self._row(request, object_id)
        cases.untagged(row)

        # from a page being typed: what it says, said again, the typing kept
        if request.headers.get("HX-Request"):
            return self.check_view(request)

        self.message_user(
            request,
            gettext("%(name)s has no tags now: batches by tag pass it by.")
            % {"name": row.name},
        )

        return HttpResponseRedirect(_back_to(request, row))

    def score_view(self, request: HttpRequest, object_id: str) -> Any:
        """The runs of the version's vignette scored where they are outstanding."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        if not self.has_change_permission(request):
            raise PermissionDenied

        row = self._row(request, object_id)
        made = cases.score_again(identity_of(request), row.trail_id)
        self.message_user(
            request,
            ngettext("%(made)d score made.", "%(made)d scores made.", made)
            % {"made": made},
        )

        return HttpResponseRedirect(_back_to(request, row))

    def check_view(self, request: HttpRequest) -> TemplateResponse | Any:
        """What saving the page would do, as it is typed."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        if not self.has_view_permission(request):
            raise PermissionDenied

        owner = identity_of(request)
        name = request.POST.get("name", "").strip()
        edited = request.POST.get("edited") or None
        since = request.POST.get("since", "")
        vignette = request.POST.get("vignette", "")
        vignette = cases.vignette_of(owner, vignette) if vignette.strip() else ""
        rows = cases.versions_of(owner, edited) if edited else []
        shown = _began(cases.Timeline(rows), since) if rows else None
        context = {
            "said": cases.said(
                owner, name, edited, int(since) if since.isdigit() else None
            ),
            "sharers": cases.sharers(owner, vignette, name, edited) if vignette else [],
            "vignette_changed": bool(shown and vignette and vignette != shown.vignette),
            "next": request.POST.get("next", ""),
            "oob": True,
        }

        return TemplateResponse(request, "portal/case/said.html", context)


def _began(timeline: cases.Timeline | None, since: str) -> cases.Version | None:
    """The version a page began from: the one it says, or else the head."""
    if timeline is None:
        return None

    if since.isdigit() and 0 < int(since) <= len(timeline.rows):
        return timeline.version(int(since))

    return timeline.head


def _asked(form: CaseForm | None) -> tuple[str, str, int | None]:
    """The name, the vignette and the version begun from, as the form holds them."""
    if form is None:
        return "", "", None

    values: Any = form.data if form.is_bound else form.initial
    since = str(values.get("since") or "")

    return (
        str(values.get("name") or ""),
        str(values.get("vignette") or ""),
        int(since) if since.isdigit() else None,
    )


def _back_to(request: HttpRequest, row: Case) -> str:
    """Where a button on a page goes back to: the page, or the version's."""
    back = request.POST.get("next", "")

    if back and url_has_allowed_host_and_scheme(back, {request.get_host()}):
        return back

    return reverse("admin:portal_case_change", args=[row.pk])


def _said_of(
    said: cases.Said, changed: bool, tags_before: list[str] | None, tags: list[str]
) -> str:
    """What a save did, as its message says."""
    values = {"name": said.name, "version": said.version, "was": said.version - 1}

    if not changed:
        if tags_before is not None and tags_before != sorted(tags):
            return (
                gettext(
                    "Its tags are saved, and nothing else changed: %(name)s stays at "
                    + "version %(was)d."
                )
                % values
            )

        return gettext("Nothing changed: %(name)s stays at version %(was)d.") % values

    match said.saving:
        case cases.Saving.SAME:
            return gettext("Saved as version %(version)d of %(name)s.") % values
        case cases.Saving.NEW:
            return gettext("Saved as a new case, %(name)s.") % values
        case cases.Saving.ONTO:
            return gettext("Saved onto %(name)s, as its version %(version)d.") % values
        case cases.Saving.BACK:
            return gettext("%(name)s is back, as its version %(version)d.") % values
