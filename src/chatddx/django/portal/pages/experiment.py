# pyright: basic
from typing import Any, cast, override

from django.contrib import admin
from django.db.models import ForeignKey, ManyToManyField, QuerySet
from django.http import Http404, HttpRequest, HttpResponseRedirect
from django.urls import reverse
from unfold.decorators import action

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identity
from chatddx.core.worker import wake_on_commit
from chatddx.django.orm.qs import qs_experiments, qs_owned_trails
from chatddx.django.portal.forms.experiment import NO_RUN, ExperimentForm
from chatddx.django.portal.mixins import ModelAdminFormWithRequest
from chatddx.django.portal.typing import TypedModelAdmin
from chatddx.history.models import ExperimentModel, RunModel
from chatddx.history.proxies import Experiment, Run, SharedExperiment, SharedRun
from chatddx.repo.families.django import TrailModel

EXPERIMENT_TRAIL_FIELDS = ("agent", "case", "expect")


class BaseExperimentAdmin(TypedModelAdmin[Experiment]):
    list_display = (
        "timestamp",
        "agent_",
        "case_",
        "expect_",
        "batch_",
        "collaborators_csv",
    )
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
        return obj.expect_label

    @admin.display(description="Batch")
    def batch_(self, obj: Experiment):
        return obj.batch_link

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

    def get_queryset(self, request: HttpRequest):
        qs = TypedModelAdmin.get_queryset(self, request)
        # batch_ links through `batch`, once per row.
        return qs_experiments(qs, request.user.username).select_related("batch")


@admin.register(Experiment)
class ExperimentAdmin(ModelAdminFormWithRequest, BaseExperimentAdmin):
    form = ExperimentForm

    show_add_link = True

    add_fields = (
        "agent",
        "case",
        "expect",
        "collaborators",
        "initial_run_status",
    )

    actions_detail = ("queue",)

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)
        return qs.filter(owner__name=request.user.username).order_by("-timestamp")

    @override
    def has_add_permission(self, request: HttpRequest):
        return True

    @override
    def get_fields(self, request: HttpRequest, obj: Experiment | None = None):
        if obj is None:
            return self.add_fields

        return super().get_fields(request, obj)

    @override
    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: Experiment | None = None,
    ):
        if obj is None:
            return ()

        return super().get_readonly_fields(request, obj)

    @override
    def formfield_for_foreignkey(
        self,
        db_field: ForeignKey[Any],
        request: HttpRequest | None,
        **kwargs: Any,
    ):
        assert request is not None

        if db_field.name in EXPERIMENT_TRAIL_FIELDS:
            trails = cast(
                QuerySet[TrailModel],
                db_field.remote_field.model._default_manager.all(),  # pyright: ignore[reportPrivateUsage]
            )
            kwargs["queryset"] = qs_owned_trails(trails, request.user.username)

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
            kwargs["queryset"] = IdentityModel.objects.exclude(
                name=request.user.username,
            )

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(
        self,
        request: HttpRequest,
        obj: Experiment,
        form: Any,
        change: bool,
    ):
        if not change:
            obj.owner = ensure_identity(request.user.username)

        super().save_model(request, obj, form, change)

        if change:
            return

        status: str = form.cleaned_data["initial_run_status"]
        if status == NO_RUN:
            return

        self._create_run(request, obj, status)

    @action(description="Queue")
    def queue(self, request: HttpRequest, object_id: int):
        """
        Queue another run of this experiment. Deliberately not idempotent: a
        second click is a second run.
        """
        try:
            experiment = self.get_queryset(request).get(pk=object_id)
        except Experiment.DoesNotExist as e:
            raise Http404 from e

        self._create_run(request, experiment, RunStatusChoices.QUEUED)

        return HttpResponseRedirect(
            reverse("admin:orm_experiment_change", args=[object_id])
        )

    def _create_run(
        self,
        request: HttpRequest,
        obj: ExperimentModel,
        status: str,
    ):
        run = RunModel.objects.create(
            owner=ensure_identity(request.user.username),
            experiment=obj,
            status=status,
        )

        if status == RunStatusChoices.QUEUED:
            wake_on_commit()

        self.message_user(
            request,
            f"Run {run.uuid} created with status {RunStatusChoices(status).label}.",
        )

        return run


@admin.register(SharedExperiment)
class SharedExperimentAdmin(BaseExperimentAdmin):
    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)
        return qs.filter(collaborators__name=request.user.username).order_by(
            "-timestamp"
        )


@admin.register(Run)
class RunAdmin(TypedModelAdmin[Run]):
    list_display = (
        "timestamp",
        "experiment_",
        "status",
        "session_",
        "result",
        "collaborators_csv",
    )
    fields = (
        "timestamp",
        "experiment",
        "status",
        "session_",
        "result_",
        "collaborators",
    )
    readonly_fields = ("timestamp", "session_", "result_")
    list_filter = ("status",)
    list_select_related = ("experiment", "session")

    actions = ("requeue",)

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)

        return qs.filter(owner__name=request.user.username).order_by("-timestamp")

    @admin.display(description="Experiment")
    def experiment_(self, obj: Run):
        return obj.experiment_link

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

        if updated:
            wake_on_commit()

        self.message_user(
            request,
            f"{updated} run(s) queued. The worker picks them up; with none "
            + "running, `chatddx worker run` processes them here and now.",
        )


@admin.register(SharedRun)
class SharedRunAdmin(RunAdmin):
    def get_queryset(self, request: HttpRequest):
        qs = TypedModelAdmin.get_queryset(self, request)

        return qs.filter(
            collaborators__name=request.user.username,
        ).order_by("-timestamp")
