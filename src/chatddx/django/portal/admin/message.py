# pyright: basic
from dataclasses import asdict
from typing import Any

from django.contrib import admin
from django.http import HttpRequest
from django.utils.safestring import mark_safe
from markdown import markdown
from unfold.utils import format_html

from chatddx.django.orm.qs import qs_messages
from chatddx.django.portal.admin.base import TypedModelAdmin
from chatddx.history.proxies import Message
from chatddx.utils import get_step_nav, render_json_html, truncate_content


@admin.register(Message)
class MessageAdmin(TypedModelAdmin[Message]):
    change_form_template: str = "templates/message.html"
    add_form_template: str = "templates/message.html"

    list_display = [
        "timestamp",
        "role",
        "content_short",
        "direction",
        "tokens",
        "agent_",
    ]
    fields = list_display + [
        "run_id",
        "get_session",
        "thinking",
        "content",
        "payload",
    ]

    ordering = ("-timestamp",)
    readonly_fields = fields

    show_add_link = False
    compressed_fields = True

    def agent_(self, obj):
        return obj.agent_link

    def get_queryset(self, request: HttpRequest):
        owner_name = request.user.username
        qs = super().get_queryset(request)
        qs = qs_messages(qs, owner_name)
        qs = qs.filter(session__owner__name=owner_name)
        return qs

    @admin.display(description="Session")
    def get_session(self, message: Message):
        return message.session_link

    def content_short(self, message: Message):
        return truncate_content(message.content, 55)  # type: ignore

    @admin.display(description="Content")
    def content(self, message: Message):
        markdown_tpl = '<div class="prose dark:prose-invert max-w-none">{}</div>'

        match message.typed_content:
            case None:
                return ""
            case str():
                html = markdown(
                    message.typed_content,
                    extensions=["fenced_code", "tables"],
                )
                return format_html(markdown_tpl, mark_safe(html))
            case _:
                return render_json_html(message.typed_content)

    def has_add_permission(self, request: HttpRequest):
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: Message | None = None,
    ):
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: Message | None = None,
    ):
        return False

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ):
        extra_context = extra_context or {}

        qs = self.get_queryset(request)

        message_model = qs.get(pk=object_id)
        qs_session = qs.filter(session_id=message_model.spec.session_id)

        step_nav = get_step_nav(message_model, qs_session)  # pyright: ignore[reportArgumentType]

        extra_context |= asdict(step_nav)

        return super().change_view(request, object_id, form_url, extra_context)
