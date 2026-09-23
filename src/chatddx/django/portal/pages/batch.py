# pyright: basic
from typing import Any, override

from django.contrib import admin, messages
from django.http import Http404, HttpRequest, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from unfold.decorators import action

from chatddx.core.choices import RunStatusChoices
from chatddx.core.utils import ensure_identity
from chatddx.django.orm.qs import qs_batches
from chatddx.django.portal.forms.batch import BatchForm
from chatddx.django.portal.mixins import ModelAdminFormWithRequest
from chatddx.django.portal.typing import TypedModelAdmin
from chatddx.history import batches
from chatddx.history.batches import BatchPlan
from chatddx.history.models import BatchModel
from chatddx.history.proxies import Batch

CONFIRM_FIELD = "_confirm_batch"

CONFIRM_TITLE = "Confirm batch"


@admin.register(Batch)
class BatchAdmin(ModelAdminFormWithRequest, TypedModelAdmin[Batch]):
    form = BatchForm

    confirmation_template = "templates/batch_confirmation.html"

    list_display = (
        "timestamp",
        "agent_",
        "case_tags_csv",
        "scorers_csv",
        "experiment_count",
    )
    fields = (
        "uuid",
        "timestamp",
        "agent_",
        "case_tags_csv",
        "scorers_csv",
        "experiment_count",
    )
    readonly_fields = fields

    add_fields = (
        "agent",
        "case_tags",
        "scorers",
        "queue_immediately",
    )

    actions_detail = ("requeue",)

    @admin.display(description="Agent")
    def agent_(self, obj: Batch):
        return obj.agent_link

    def get_queryset(self, request: HttpRequest):
        qs = TypedModelAdmin.get_queryset(self, request)

        return (
            qs_batches(qs, request.user.username)
            .filter(owner__name=request.user.username)
            .order_by("-timestamp")
        )

    @override
    def has_change_permission(self, request: HttpRequest, obj: Batch | None = None):
        return False

    @override
    def has_delete_permission(self, request: HttpRequest, obj: Batch | None = None):
        return False

    @override
    def get_fields(self, request: HttpRequest, obj: Batch | None = None):
        if obj is None:
            return self.add_fields

        return super().get_fields(request, obj)

    @override
    def get_readonly_fields(self, request: HttpRequest, obj: Batch | None = None):
        if obj is None:
            return ()

        return super().get_readonly_fields(request, obj)

    @override
    def add_view(
        self,
        request: HttpRequest,
        form_url: str = "",
        extra_context: Any = None,
    ):
        """
        The add form, with the confirmation page in front of the save.

        A post that hasn't been through the confirmation page yet is planned
        rather than saved, and comes back as the page the user confirms; the
        post that page makes carries the same data plus `CONFIRM_FIELD`, and
        falls through to the ordinary add.
        """
        if (
            request.method != "POST"
            or CONFIRM_FIELD in request.POST
            or not self.has_add_permission(request)
        ):
            return super().add_view(request, form_url, extra_context)

        form = self.get_form(request)(request.POST)

        if not form.is_valid():
            return super().add_view(request, form_url, extra_context)

        queued = bool(form.cleaned_data["queue_immediately"])

        plan = batches.plan(
            request.user.username,
            form.cleaned_data["agent"],
            list(form.cleaned_data["case_tags"]),
            list(form.cleaned_data["scorers"]),
        )

        return self._confirmation(
            request,
            plan,
            headline=(
                f"Generating this batch creates {plan.total} experiment(s), "
                + (
                    "queued to run straight away."
                    if queued
                    else "stored without running."
                )
            ),
            confirm_label="Yes, generate them",
            cancel_url=self._changelist_url(),
        )

    def save_model(self, request: HttpRequest, obj: Batch, form: Any, change: bool):
        if not change:
            obj.owner = ensure_identity(request.user.username)

        super().save_model(request, obj, form, change)

    def save_related(
        self,
        request: HttpRequest,
        form: Any,
        formsets: Any,
        change: bool,
    ):
        super().save_related(request, form, formsets, change)

        if change:
            return

        status = (
            RunStatusChoices.QUEUED
            if form.cleaned_data["queue_immediately"]
            else RunStatusChoices.STORED
        )

        self._generate(request, form.instance, status)

    @action(description="Re-queue")
    def requeue(self, request: HttpRequest, object_id: int):
        """
        Generate another set of experiments from this batch, queued to run.

        Deliberately not idempotent: a second click is a second set, the way
        a second click on an experiment's queue button is a second run. The
        confirmation page is what stands between the two.
        """
        try:
            batch = self.get_queryset(request).get(pk=object_id)
        except Batch.DoesNotExist as e:
            raise Http404 from e

        change_url = reverse("admin:orm_batch_change", args=[object_id])

        if request.method == "POST" and CONFIRM_FIELD in request.POST:
            self._generate(request, batch, RunStatusChoices.QUEUED)

            return HttpResponseRedirect(change_url)

        plan = batches.plan_for(batch)

        return self._confirmation(
            request,
            plan,
            headline=(
                f"Re-queueing this batch creates {plan.total} experiment(s), "
                "queued to run straight away."
            ),
            confirm_label="Yes, queue them",
            cancel_url=change_url,
        )

    def _confirmation(
        self,
        request: HttpRequest,
        plan: BatchPlan,
        headline: str,
        confirm_label: str,
        cancel_url: str,
    ):
        context = {
            **self.admin_site.each_context(request),
            "title": CONFIRM_TITLE,
            "headline": headline,
            "opts": self.opts,
            "plan": plan,
            "hidden": [
                (name, value)
                for name, values in request.POST.lists()
                if name != "csrfmiddlewaretoken"
                for value in values
            ],
            "confirm_field": CONFIRM_FIELD,
            "confirm_label": confirm_label,
            "cancel_url": cancel_url,
            "action_url": request.get_full_path(),
        }

        return TemplateResponse(request, self.confirmation_template, context)

    def _generate(self, request: HttpRequest, batch: BatchModel, status: str):
        generated = batches.generate(batch, status)
        label = RunStatusChoices(status).label

        self.message_user(
            request,
            f"{len(generated.experiments)} experiment(s) generated, "
            f"each with a run at {label}.",
        )

        excluded = batches.excluded_message(generated.plan)

        if excluded:
            self.message_user(request, excluded, messages.WARNING)

        return generated

    def _changelist_url(self):
        return reverse("admin:orm_batch_changelist")
