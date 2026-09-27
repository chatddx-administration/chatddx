# pyright: basic
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
from django.db import transaction
from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.http import (
    Http404,
    HttpRequest,
    HttpResponseNotAllowed,
    HttpResponseRedirect,
)
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.formats import date_format
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _, ngettext
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from chatddx.bench.cell import SLICES
from chatddx.django.portal import batches, status
from chatddx.django.portal.case_admin import CaseAdmin
from chatddx.django.portal.configuration_admin import ConfigurationAdmin
from chatddx.django.portal.forms import CASES_FORM, BatchForm, CasesForm
from chatddx.django.portal.models import (
    Batch,
    Case,
    Configuration,
    Run,
    Sampling,
    Stack,
)
from chatddx.django.portal.owners import bench_of, identity_of
from chatddx.django.portal.run_admin import RunAdmin
from chatddx.django.portal.sampling_admin import SamplingAdmin
from chatddx.django.portal.stack_admin import StackAdmin
from chatddx.worker import control, queue
from chatddx.worker.models import STOPPED_BY, JobModel, Status

CONFIRM = "_confirm"
RUN, LATER = "run", "later"

SEVERAL = ("case_tags", *SLICES)

CONTROLS = {"pause": control.pause, "resume": control.resume, "stop": control.stop}

RUN_FORM = "batch-run"

Batch._meta.verbose_name = _("batch")
Batch._meta.verbose_name_plural = _("batches")

admin.site.unregister(User)
admin.site.unregister(Group)
admin.site.register(Case, CaseAdmin)
admin.site.register(Configuration, ConfigurationAdmin)
admin.site.register(Run, RunAdmin)
admin.site.register(Sampling, SamplingAdmin)
admin.site.register(Stack, StackAdmin)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


def _jobs(**filters: Any) -> Any:
    return Coalesce(
        Subquery(
            JobModel.objects.filter(batch=OuterRef("uuid"), **filters)
            .order_by()
            .values("batch")
            .annotate(count=Count("pk"))
            .values("count")
        ),
        0,
    )


def counts_of(batch: Any) -> queue.Counts:
    counted = {
        name: getattr(batch, f"jobs_{name}", 0)
        for name in ("stored", "queued", "running", "completed", "stopped")
    }
    total = getattr(batch, "jobs_total", 0)

    return queue.Counts(total, **counted, failed=total - sum(counted.values()))


@admin.register(Batch)
class BatchAdmin(ModelAdmin):
    form = BatchForm
    change_form_template = "portal/batch/change_form.html"
    confirmation_template = "portal/batch/confirmation.html"

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
        "state_",
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
        "state_",
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

    @admin.display(description=_("State"))
    def state_(self, batch: Batch) -> str:
        counts = counts_of(batch)
        state = status.state_of(counts)
        said = str(status.STATES[state])

        if state == status.BatchState.STORED:
            return said

        return _("%(state)s · %(completed)d of %(total)d") % {
            "state": said,
            "completed": counts.completed,
            "total": counts.total,
        }

    @override
    def get_queryset(self, request: HttpRequest) -> Any:
        return (
            super()
            .get_queryset(request)
            .filter(owner__name=identity_of(request))
            .annotate(
                jobs_total=_jobs(),
                jobs_stored=_jobs(status=Status.STORED),
                jobs_queued=_jobs(status=Status.QUEUED),
                jobs_running=_jobs(status=Status.RUNNING),
                jobs_completed=_jobs(status=Status.COMPLETED),
                jobs_stopped=_jobs(status__in=STOPPED_BY),
            )
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

        return type(form.__name__, (form,), {"bench": bench_of(request)})

    @override
    def get_changeform_initial_data(self, request: HttpRequest) -> dict[str, Any]:
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
        if request.method == "POST" and self.has_add_permission(request):
            form = self.get_form(request)(request.POST)

            if form.is_valid() and (
                request.POST.get(CONFIRM) not in (RUN, LATER) or not form.plan.trials
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
                    "No configuration of yours yet: `chatddx init-data %(name)s "
                    + "--with-giftbag` gives you the archive's to start from."
                )
                % {"name": form.bench.identity},
                messages.WARNING,
            )
        elif add and not form.fields["case_tags"].choices:
            self.message_user(
                request,
                _("No case of yours has a tag yet: a batch runs the cases tagged so."),
                messages.WARNING,
            )

        if obj is not None:
            cases = CasesForm(bench_of(request), obj)
            context["media"] = context["media"] + cases.media
            context.update(self._batch_page(request, obj, cases))

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
            "shown": batches.shown(plan, identity_of(request)),
            "scorers": batches.scorers_of(form.bench, plan),
            "asked": asked,
            "back_url": f"{reverse('admin:portal_batch_add')}?{urlencode(asked)}",
            "action_url": request.get_full_path(),
            "confirm": CONFIRM,
            "run": RUN,
            "later": LATER,
        }

        return TemplateResponse(request, self.confirmation_template, context)

    @override
    def save_model(
        self, request: HttpRequest, obj: Any, form: Any, change: bool
    ) -> None:
        super().save_model(request, obj, form, change)

        if not change:
            _ = batches.put(obj, run=request.POST.get(CONFIRM) == RUN)

    @override
    def response_add(
        self, request: HttpRequest, obj: Any, post_url_continue: Any = None
    ) -> Any:
        said = {
            "batch": self.batch_(obj),
            "trials": obj.trials,
            "cells": len(obj.cells),
            "cases": len(obj.cases),
        }

        if request.POST.get(CONFIRM) == RUN:
            kept = ngettext(
                "Batch %(batch)s is kept, and its %(trials)d trial queued for the "
                + "worker: %(cells)d × %(cases)d.",
                "Batch %(batch)s is kept, and its %(trials)d trials queued for the "
                + "worker: %(cells)d × %(cases)d.",
                obj.trials,
            )
            self.message_user(
                request,
                format_html(
                    '{} <a class="font-semibold underline" href="{}">{}</a>',
                    kept % said,
                    reverse("admin:portal_batch_status"),
                    _("Follow them on the status page."),
                ),
            )
        else:
            kept = ngettext(
                "Batch %(batch)s is kept for later, its %(trials)d trial stored: "
                + "%(cells)d × %(cases)d. Run it from here.",
                "Batch %(batch)s is kept for later, its %(trials)d trials stored: "
                + "%(cells)d × %(cases)d. Run it from here.",
                obj.trials,
            )
            self.message_user(request, kept % said)

        return HttpResponseRedirect(reverse("admin:portal_batch_change", args=[obj.pk]))

    @override
    def get_urls(self) -> Any:
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
            path(
                "<path:object_id>/state/",
                self.admin_site.admin_view(self.state_view),
                name="portal_batch_state",
            ),
            path(
                "<path:object_id>/run/",
                self.admin_site.admin_view(self.run_view),
                name="portal_batch_run",
            ),
            path(
                "<path:object_id>/cases/",
                self.admin_site.admin_view(self.cases_view),
                name="portal_batch_cases",
            ),
            *super().get_urls(),
        ]

    def _batch(self, request: HttpRequest, object_id: str) -> Any:
        if not self.has_view_permission(request):
            raise PermissionDenied

        batch = self.get_object(request, unquote(object_id))

        if batch is None:
            raise Http404

        return batch

    def _batch_page(
        self, request: HttpRequest, batch: Any, cases: CasesForm
    ) -> dict[str, Any]:
        return {
            "shown": batches.Shown.of(
                batch.configuration,
                batch.cells,
                batch.held_back,
                batch.cases,
                batch.seed,
                identity_of(request),
            ),
            "cases_form": cases,
            "cases_form_id": CASES_FORM,
            "cases_url": reverse("admin:portal_batch_cases", args=[batch.pk]),
            **self._state(request, batch),
        }

    def _state(self, request: HttpRequest, batch: Any) -> dict[str, Any]:
        return {
            "batch_shown": status.batch_shown(identity_of(request), batch),
            "can_run": self.has_add_permission(request),
            "run_form_id": RUN_FORM,
            "run_url": reverse("admin:portal_batch_run", args=[batch.pk]),
            "state_url": reverse("admin:portal_batch_state", args=[batch.pk]),
        }

    def state_view(self, request: HttpRequest, object_id: str) -> TemplateResponse:
        batch = self._batch(request, object_id)

        return TemplateResponse(
            request, "portal/batch/state_panel.html", self._state(request, batch)
        )

    def run_view(self, request: HttpRequest, object_id: str) -> Any:
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        batch = self._batch(request, object_id)

        if not self.has_add_permission(request):
            raise PermissionDenied

        owner = identity_of(request)

        match request.POST.get("action"):
            case "resume" if not JobModel.objects.filter(batch=batch.uuid).exists():
                queued = batches.put(batch, run=True)
            case "resume":
                queued = queue.resume(owner, batch.uuid)
            case "rerun":
                queued = queue.rerun(owner, batch.uuid)
            case _:
                queued = 0

        self.message_user(
            request,
            ngettext(
                "%(queued)d trial of the batch queued for the worker.",
                "%(queued)d trials of the batch queued for the worker.",
                queued,
            )
            % {"queued": queued},
            messages.SUCCESS if queued else messages.WARNING,
        )

        return HttpResponseRedirect(
            reverse("admin:portal_batch_change", args=[batch.pk])
        )

    def cases_view(self, request: HttpRequest, object_id: str) -> Any:
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        batch = self._batch(request, object_id)

        if not self.has_add_permission(request):
            raise PermissionDenied

        form = CasesForm(bench_of(request), batch, request.POST)
        back = HttpResponseRedirect(
            reverse("admin:portal_batch_change", args=[batch.pk])
        )

        if not form.is_valid():
            for errors in form.errors.values():
                for error in errors:
                    self.message_user(request, str(error), messages.WARNING)

            return back

        added = form.unheld
        run = queue.counts([batch.uuid]).under_way > 0

        with transaction.atomic():
            batch.cases = batch.cases + batches.cases_of(added)
            batch.tags = sorted({*batch.tags, *form.cleaned_data["case_tags"]})
            batch.save(update_fields=["cases", "tags"])
            trials = queue.put(
                batch.owner.name, batch.uuid, batches.kept_of(batch), added, run
            )

        cases = ngettext(
            "%(cases)d case added", "%(cases)d cases added", len(added)
        ) % {"cases": len(added)}
        trials = (
            ngettext(
                "%(trials)d trial queued behind the batch's.",
                "%(trials)d trials queued behind the batch's.",
                trials,
            )
            if run
            else ngettext(
                "%(trials)d trial stored till the batch is run.",
                "%(trials)d trials stored till the batch is run.",
                trials,
            )
        ) % {"trials": trials}
        self.message_user(request, f"{cases}: {trials}")

        return back

    def status_view(self, request: HttpRequest) -> TemplateResponse:
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
        if not self.has_view_permission(request):
            raise PermissionDenied

        return TemplateResponse(
            request, "portal/batch/status_panel.html", self._panel(request)
        )

    def control_view(self, request: HttpRequest) -> Any:
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        if not self.has_add_permission(request):
            raise PermissionDenied

        action = CONTROLS.get(request.POST.get("action", ""))

        if action is not None:
            _ = action(identity_of(request))

        if request.headers.get("HX-Request"):
            return self.panel_view(request)

        return HttpResponseRedirect(reverse("admin:portal_batch_status"))

    def _panel(self, request: HttpRequest) -> dict[str, Any]:
        return {
            "shown": status.shown(identity_of(request)),
            "can_control": self.has_add_permission(request),
            "panel_url": reverse("admin:portal_batch_status_panel"),
            "control_url": reverse("admin:portal_batch_status_control"),
            "change_url": reverse("admin:portal_batch_changelist"),
        }
