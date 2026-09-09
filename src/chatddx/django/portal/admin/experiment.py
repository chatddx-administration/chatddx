# pyright: basic
from typing import override

from django.contrib import admin
from django.http import HttpRequest

from chatddx.django.portal.admin.base import TypedModelAdmin
from chatddx.experiment.proxies import Experiment, SharedExperiment


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
