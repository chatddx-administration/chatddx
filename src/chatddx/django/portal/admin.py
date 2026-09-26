# pyright: basic
"""
The portal's pages: the Batch, which plans the repl's batch with its slices
varied, confirms the plan, keeps it and puts it in the worker's queue; the
status of the worker at its queue, to pause, resume and stop it; and the
admin's users and groups, in unfold's dress.
"""

from typing import Any, ClassVar, override
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.contrib.auth.admin import (
    GroupAdmin as BaseGroupAdmin,
    UserAdmin as BaseUserAdmin,
)
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.formats import date_format
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _, ngettext
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from chatddx.bench.bench import Bench
from chatddx.bench.cell import SLICES
from chatddx.core.utils import ensure_identity
from chatddx.django.portal import batches, status
from chatddx.django.portal.forms import BatchForm
from chatddx.django.portal.models import Batch
from chatddx.worker import control, queue
from chatddx.worker.models import FINISHED, QueuedModel

# what the confirmation's post carries: that post alone saves a batch
CONFIRM = "_confirm"

# the add form's fields that take several values, from its query as well
SEVERAL = ("case_tags", *SLICES)

# what the status page's buttons ask of the worker
CONTROLS = {"pause": control.pause, "resume": control.resume, "stop": control.stop}

# what the portal calls a batch, for the model holds no words of the portal's
Batch._meta.verbose_name = _("batch")
Batch._meta.verbose_name_plural = _("batches")

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


def identity_of(request: HttpRequest) -> str:
    """The identity a request acts as: its user's, by name."""
    return ensure_identity(request.user.get_username()).name


@admin.register(Batch)
class BatchAdmin(ModelAdmin):
    form = BatchForm
    change_form_template = "portal/batch/change_form.html"
    confirmation_template = "portal/batch/confirmation.html"

    # the slices come in once there are cases to run them on
    conditional_fields: ClassVar[dict[str, str]] = {
        entity: "case_tags && case_tags.length" for entity in SLICES
    }

    add_fieldsets = (
        (None, {"fields": ("configuration", "stack", "case_tags", "seed")}),
        (
            _("Variations"),
            {
                "fields": SLICES,
                "description": _(
                    "The configuration's own are ticked. Tick more, and the batch "
                    + "runs every combination of what is ticked."
                ),
            },
        ),
    )
    readonly_fields = (
        "batch_",
        "when_",
        "cell_",
        "tags_",
        "varied_",
        "seed_",
        "ran_",
    )
    fieldsets = ((None, {"fields": readonly_fields}),)
    list_display = (
        "batch_",
        "when_",
        "cell_",
        "tags_",
        "cells_",
        "cases_",
        "trials_",
        "ran_",
        "seed_",
    )
    list_display_links = ("batch_",)

    @admin.display(description=_("Batch"))
    def batch_(self, batch: Batch) -> str:
        return str(batch.uuid)[:8]

    @admin.display(description=_("When"), ordering="timestamp")
    def when_(self, batch: Batch) -> str:
        return date_format(localtime(batch.timestamp), "DATETIME_FORMAT")

    @admin.display(description=_("Configuration × stack"))
    def cell_(self, batch: Batch) -> str:
        return f"{batch.configuration} × {batch.stack}"

    @admin.display(description=_("Case tags"))
    def tags_(self, batch: Batch) -> str:
        return ", ".join(batch.tags)

    @admin.display(description=_("Varied"))
    def varied_(self, batch: Batch) -> str:
        """What was ticked of each slice a cell sets in place of the configuration's."""
        varied = {
            entity for cell in batch.cells + batch.held_back for entity in cell["set"]
        }

        return (
            "; ".join(
                f"{entity}: {', '.join(batch.variations.get(entity, []))}"
                for entity in SLICES
                if entity in varied
            )
            or "—"
        )

    @admin.display(description=_("Cells"))
    def cells_(self, batch: Batch) -> str:
        held_back = len(batch.held_back)
        cells = str(len(batch.cells))

        return f"{cells} ({held_back} held back)" if held_back else cells

    @admin.display(description=_("Cases"))
    def cases_(self, batch: Batch) -> int:
        return len(batch.cases)

    @admin.display(description=_("Trials"))
    def trials_(self, batch: Batch) -> int:
        return batch.trials

    @admin.display(description=_("Seed"))
    def seed_(self, batch: Batch) -> str:
        return "none" if batch.seed is None else f"#{batch.seed}"

    @admin.display(description=_("Ran"))
    def ran_(self, batch: Batch) -> str:
        """How many of its trials the worker has taken up, of how many."""
        return f"{getattr(batch, 'ran', 0)} of {batch.trials}"

    @override
    def get_queryset(self, request: HttpRequest) -> Any:
        ran = (
            QueuedModel.objects.filter(batch=OuterRef("uuid"), status__in=FINISHED)
            .order_by()
            .values("batch")
            .annotate(count=Count("pk"))
            .values("count")
        )

        return (
            super()
            .get_queryset(request)
            .filter(owner__name=identity_of(request))
            .annotate(ran=Coalesce(Subquery(ran), 0))
        )

    @override
    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    @override
    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    @override
    def get_fieldsets(self, request: HttpRequest, obj: Any = None) -> Any:
        return (
            self.add_fieldsets if obj is None else super().get_fieldsets(request, obj)
        )

    @override
    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> Any:
        return () if obj is None else super().get_readonly_fields(request, obj)

    @override
    def get_form(
        self, request: HttpRequest, obj: Any = None, change: bool = False, **kwargs: Any
    ) -> Any:
        form = super().get_form(request, obj, change, **kwargs)

        return type(form.__name__, (form,), {"bench": Bench(identity_of(request))})

    @override
    def get_changeform_initial_data(self, request: HttpRequest) -> dict[str, Any]:
        """What a query asks of the add form: a batch to plan again, say."""
        return {
            name: values if name in SEVERAL else values[-1]
            for name, values in request.GET.lists()
        }

    @override
    def add_view(
        self,
        request: HttpRequest,
        form_url: str = "",
        extra_context: Any = None,
    ) -> Any:
        """
        The add form, with the plan to confirm in front of the save: a post
        that comes out valid is shown its plan, and saved only once the
        confirmation posts it back, with something in it to run.
        """
        if request.method == "POST" and self.has_add_permission(request):
            form = self.get_form(request)(request.POST)

            if form.is_valid() and (
                CONFIRM not in request.POST or not form.plan.trials
            ):
                return self._confirmation(request, form)

        return super().add_view(request, form_url, extra_context)

    @override
    def render_change_form(
        self,
        request: HttpRequest,
        context: Any,
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: Any = None,
    ) -> Any:
        form = context["adminform"].form

        if add and len(form.fields["configuration"].choices) == 1:
            self.message_user(
                request,
                _(
                    "Nothing to use yet: `chatddx init-data %(name)s` shares the "
                    + "archive's inventory with you."
                )
                % {"name": form.bench.identity},
                messages.WARNING,
            )

        return super().render_change_form(request, context, add, change, form_url, obj)

    def _confirmation(self, request: HttpRequest, form: Any) -> TemplateResponse:
        plan = form.plan
        asked = [
            (name, value)
            for name, values in request.POST.lists()
            if name not in ("csrfmiddlewaretoken", CONFIRM)
            for value in values
        ]
        context = {
            **self.admin_site.each_context(request),
            "title": _("Confirm the batch"),
            "opts": self.opts,
            "plan": plan,
            "description": plan.description,
            "shown": batches.shown(plan),
            "scorers": batches.scorers_of(form.bench, plan),
            "asked": asked,
            "back_url": f"{reverse('admin:portal_batch_add')}?{urlencode(asked)}",
            "action_url": request.get_full_path(),
            "confirm": CONFIRM,
        }

        return TemplateResponse(request, self.confirmation_template, context)

    @override
    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: Any = None,
    ) -> Any:
        batch = self.get_object(request, unquote(object_id))

        if batch is not None:
            shown = batches.Shown.of(
                batch.configuration,
                batch.cells,
                batch.held_back,
                batch.cases,
                batch.seed,
            )
            extra_context = {**(extra_context or {}), "shown": shown}

        return super().change_view(request, object_id, form_url, extra_context)

    @override
    def save_model(
        self, request: HttpRequest, obj: Any, form: Any, change: bool
    ) -> None:
        super().save_model(request, obj, form, change)

        if not change:
            _ = queue.put(form.bench.identity, form.plan, batch=obj.uuid)

    @override
    def response_add(
        self, request: HttpRequest, obj: Any, post_url_continue: Any = None
    ) -> Any:
        kept = ngettext(
            "Batch %(batch)s is kept, and its %(trials)d trial queued for the "
            + "worker: %(cells)d × %(cases)d.",
            "Batch %(batch)s is kept, and its %(trials)d trials queued for the "
            + "worker: %(cells)d × %(cases)d.",
            obj.trials,
        ) % {
            "batch": self.batch_(obj),
            "trials": obj.trials,
            "cells": len(obj.cells),
            "cases": len(obj.cases),
        }
        self.message_user(
            request,
            format_html(
                '{} <a class="font-semibold underline" href="{}">{}</a>',
                kept,
                reverse("admin:portal_batch_status"),
                _("Follow them on the status page."),
            ),
        )

        return HttpResponseRedirect(reverse("admin:portal_batch_change", args=[obj.pk]))

    @override
    def get_urls(self) -> Any:
        # before the admin's own, whose object_id would take "status" for one
        return [
            path(
                "status/",
                self.admin_site.admin_view(self.status_view),
                name="portal_batch_status",
            ),
            path(
                "status/panel/",
                self.admin_site.admin_view(self.panel_view),
                name="portal_batch_status_panel",
            ),
            path(
                "status/control/",
                self.admin_site.admin_view(self.control_view),
                name="portal_batch_status_control",
            ),
            *super().get_urls(),
        ]

    def status_view(self, request: HttpRequest) -> TemplateResponse:
        """The worker at its queue, whatever batches it came from."""
        if not self.has_view_permission(request):
            raise PermissionDenied

        context = {
            **self.admin_site.each_context(request),
            "title": _("Status"),
            "opts": self.opts,
            **self._panel(request),
        }

        return TemplateResponse(request, "portal/batch/status.html", context)

    def panel_view(self, request: HttpRequest) -> TemplateResponse:
        """The status, as the page asks for it again every second."""
        if not self.has_view_permission(request):
            raise PermissionDenied

        return TemplateResponse(
            request, "portal/batch/status_panel.html", self._panel(request)
        )

    def control_view(self, request: HttpRequest) -> Any:
        """Pause, resume or stop the worker, as the page's buttons ask."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        if not self.has_add_permission(request):
            raise PermissionDenied

        action = CONTROLS.get(request.POST.get("action", ""))

        if action is not None:
            _ = action()

        if request.headers.get("HX-Request"):
            return self.panel_view(request)

        return HttpResponseRedirect(reverse("admin:portal_batch_status"))

    def _panel(self, request: HttpRequest) -> dict[str, Any]:
        return {
            "shown": status.shown(),
            "identity": identity_of(request),
            "can_control": self.has_add_permission(request),
            "panel_url": reverse("admin:portal_batch_status_panel"),
            "control_url": reverse("admin:portal_batch_status_control"),
        }
