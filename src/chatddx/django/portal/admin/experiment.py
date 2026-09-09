# pyright: basic
from typing import Any, override

from django import forms
from django.contrib import admin
from django.db.models import ForeignKey, JSONField, QuerySet
from django.http import HttpRequest

from chatddx.core.choices import RunStatusChoices
from chatddx.django.portal.admin.base import TypedModelAdmin
from chatddx.django.portal.admin.utils import qs_experiments
from chatddx.experiment.proxies import Experiment, Run, SharedExperiment, SharedRun
from chatddx.history.proxies import Session
from chatddx.repo.shufflers.main import ensure_identity


class BlankableJSONField(forms.JSONField):
    """Like forms.JSONField, but renders an unset value as an empty
    widget instead of the literal text "null". Round-tripping is unaffected:
    to_python() already treats an empty submission as None (Run.result is
    null=True, blank=True), so this only changes what's displayed, not
    what's saved.
    """

    @override
    def prepare_value(self, value: Any) -> Any:
        if value is None:
            return ""
        return super().prepare_value(value)


@admin.register(Experiment)
class ExperimentAdmin(TypedModelAdmin[Experiment]):
    list_display = [
        "timestamp",
        "tags_display",
        "agent_",
        "case_",
        "expect_",
        "scorer",
        "collaborators_csv",
    ]
    fields = list_display
    readonly_fields = fields

    show_add_link = False

    @admin.display(description="Agent")
    def agent_(self, obj: Experiment):
        return obj.agent_link

    @admin.display(description="Case")
    def case_(self, obj: Experiment):
        return obj.case_link

    @admin.display(description="Expect")
    def expect_(self, obj: Experiment):
        return obj.expect_link

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)
        qs = qs.filter(owner__name=request.user.username).order_by("-timestamp")

        return qs_experiments(qs, request.user.username)

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
        qs = qs.filter(collaborators__name=request.user.username).order_by("-timestamp")

        return qs_experiments(qs, request.user.username)


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
    formfield_overrides = {
        JSONField: {"form_class": BlankableJSONField},
    }

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

        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)

        if db_field.name == "experiment":
            formfield.label_from_instance = self._experiment_label

        return formfield

    @staticmethod
    def _experiment_label(obj: Experiment) -> str:
        timestamp = obj.timestamp.strftime("%Y-%m-%d %H:%M")
        tags = obj.tags_display() or "no tags"
        return f"{timestamp} — {tags}"

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
