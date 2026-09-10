# pyright: basic
from typing import Any, override

from django.contrib import admin
from django.db.models import Max, Min
from django.http import HttpRequest

from chatddx.django.orm.qs import qs_messages
from chatddx.django.portal.admin.base import TypedModelAdmin
from chatddx.history.proxies import Message, Session, SharedSession


@admin.register(Session)
class SessionAdmin(TypedModelAdmin[Session]):
    change_form_template: str = "templates/session.html"
    add_form_template: str = "templates/session.html"
    fields = [
        "timestamp",
        "context",
        "description",
        "status",
        "total_tokens",
        "processing_time",
        "message_count",
        "collaborators",
    ]

    readonly_fields = [f for f in fields if f not in ["description", "collaborators"]]

    list_display = [f for f in fields if f not in ["collaborators"]] + [
        "collaborators_csv"
    ]

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)

        return (
            qs.filter(
                owner__name=request.user.username,
            )
            .annotate(
                annotated_earliest=Min("messages__timestamp"),
                annotated_latest=Max("messages__timestamp"),
            )
            .order_by("-timestamp")
        )

    @override
    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ):
        extra_context = extra_context or {}

        if object_id:
            extra_context["related_messages"] = qs_messages(
                Message.objects.filter(session_id=object_id),
                owner_name=request.user.username,
            )

        return super().change_view(
            request,
            object_id,
            form_url,
            extra_context=extra_context,
        )


@admin.register(SharedSession)
class SharedSessionAdmin(SessionAdmin):
    fields = SessionAdmin.list_display
    readonly_fields = [f for f in fields if f not in ["description", "collaborators"]]

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)

        return (
            qs.filter(
                collaborators__name=request.user.username,
            )
            .annotate(
                annotated_earliest=Min("messages__timestamp"),
                annotated_latest=Max("messages__timestamp"),
            )
            .order_by("-timestamp")
        )
