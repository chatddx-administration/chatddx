# pyright: basic
from typing import Any, override

from django.contrib import admin
from django.db.models import ForeignKey, QuerySet
from django.http import HttpRequest

from chatddx.core.choices import RunStatusChoices
from chatddx.django.portal.admin.base import TypedModelAdmin
from chatddx.experiment.proxies import Experiment, Run, SharedExperiment, SharedRun
from chatddx.history.proxies import Session
from chatddx.repo.shufflers.main import ensure_identity


@admin.register(Experiment)
class ExperimentAdmin(TypedModelAdmin[Experiment]):
    list_display = [
        "timestamp",
        "tags_display",
        "agent",
        "case",
        "expect",
        "scorer",
        "collaborators_csv",
    ]
    fields = list_display
    readonly_fields = fields

    show_add_link = False

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)

        return qs.filter(owner__name=request.user.username).order_by("-timestamp")

    @override
    def has_add_permission(self, request: HttpRequest):
        return False

    @override
    def has_change_permission(
        self,
        request: HttpRequest,
        obj: Experiment | None = None,
    ):
        return False

    @override
    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: Experiment | None = None,
    ):
        return False


@admin.register(SharedExperiment)
class SharedExperimentAdmin(ExperimentAdmin):
    def get_queryset(self, request: HttpRequest):
        qs = TypedModelAdmin.get_queryset(self, request)

        return qs.filter(
            collaborators__name=request.user.username,
        ).order_by("-timestamp")


@admin.register(Run)
class RunAdmin(TypedModelAdmin[Run]):
    """Runs aren't produced by any product flow yet (see
    chatddx.experiment.worker) -- this is where one gets created, requeued,
    or inspected by hand for testing/troubleshooting the worker."""

    list_display = [
        "timestamp",
        "experiment",
        "status",
        "session",
        "result",
        "collaborators_csv",
    ]
    fields = [
        "timestamp",
        "experiment",
        "status",
        "session",
        "result",
        "collaborators",
    ]
    readonly_fields = ["timestamp"]
    list_filter = ["status"]

    actions = ["requeue"]

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)

        return qs.filter(owner__name=request.user.username).order_by("-timestamp")

    @override
    def formfield_for_foreignkey(
        self,
        db_field: ForeignKey[Any],
        request: HttpRequest | None,
        **kwargs: Any,
    ):
        assert request is not None

        if db_field.name == "experiment":
            kwargs["queryset"] = Experiment.objects.filter(
                owner__name=request.user.username,
            )
        elif db_field.name == "session":
            kwargs["queryset"] = Session.objects.filter(
                owner__name=request.user.username,
            )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request: HttpRequest, obj: Run, form: Any, change: bool):
        if not change:
            obj.owner = ensure_identity(request.user.username)

        super().save_model(request, obj, form, change)

    @admin.action(description="Queue selected runs")
    def requeue(self, request: HttpRequest, queryset: QuerySet[Run]):
        updated = queryset.update(status=RunStatusChoices.QUEUED)
        self.message_user(
            request,
            f"{updated} run(s) queued. Run `chatddx worker run` to process them.",
        )


@admin.register(SharedRun)
class SharedRunAdmin(RunAdmin):
    def get_queryset(self, request: HttpRequest):
        qs = TypedModelAdmin.get_queryset(self, request)

        return qs.filter(
            collaborators__name=request.user.username,
        ).order_by("-timestamp")
