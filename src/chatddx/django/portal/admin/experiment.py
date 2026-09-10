# pyright: basic
from typing import Any, override

from django.contrib import admin
from django.db.models import ForeignKey, ManyToManyField, QuerySet
from django.http import HttpRequest

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.django.orm.qs import qs_experiments
from chatddx.django.portal.admin.base import TypedModelAdmin
from chatddx.experiment.proxies import Experiment, Run, SharedExperiment, SharedRun
from chatddx.repo.shufflers.main import ensure_identity


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
    list_display = [
        "timestamp",
        "experiment_",
        "status",
        "session",
        "result",
        "collaborators_csv",
    ]
    fields = [
        "timestamp",
        "experiment",
        "status",
        "session_",
        "result_",
        "collaborators",
    ]
    readonly_fields = ["timestamp", "session_", "result_"]
    list_filter = ["status"]

    actions = ["requeue"]

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)

        return qs.filter(owner__name=request.user.username).order_by("-timestamp")

    @admin.display(description="Experiment")
    def experiment_(self, obj: Run):
        return Experiment.objects.get(pk=obj.experiment_id)

    @admin.display(description="Session")
    def session_(self, obj: Run):
        return obj.session_link

    @admin.display(description="Result")
    def result_(self, obj: Run):
        return obj.result_html

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

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @override
    def formfield_for_manytomany(
        self,
        db_field: ManyToManyField,
        request: HttpRequest | None,
        **kwargs: Any,
    ):
        assert request is not None

        if db_field.name == "collaborators":
            # The Run's owner is implicit -- they already have full access
            # to it -- so they shouldn't show up as a choice in their own
            # collaborators picker. Nothing stops a collaborator set from
            # containing the owner (e.g. a Run shared back to its owner by
            # someone else), this just keeps the owner off the default list
            # of people *to add*.
            kwargs["queryset"] = IdentityModel.objects.exclude(
                name=request.user.username,
            )

        return super().formfield_for_manytomany(db_field, request, **kwargs)

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
