# pyright: basic
import json
from datetime import timedelta
from functools import cached_property
from typing import cast, final, override

import jsonschema
from django.contrib import admin
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from pydantic_ai import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from chatddx.core.choices import MessageKindChoices, RoleChoices
from chatddx.history.models import MessageModel, SessionModel
from chatddx.history.schemas import ErrorPayload, MessageSpec, PromptPayload
from chatddx.repo.trail_cache import trail_cache
from chatddx.repo.trail_specs import AgentSpec
from chatddx.runtime.utils import get_part_content
from chatddx.utils import truncate_content


class Session(SessionModel):
    @final
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Session"
        verbose_name_plural = "Sessions"

    @override
    def __str__(self):
        if self.description:
            return self.description[:100]
        return f"[{self.uuid}]"

    @admin.display(description="Tokens")
    def total_tokens(self):
        tokens = 0
        for message in self.messages.all():
            if "usage" in message.payload:
                tokens += message.payload["usage"].get("input_tokens", 0)
                tokens += message.payload["usage"].get("output_tokens", 0)
        return tokens

    @admin.display(description="Messages")
    def message_count(self):
        return self.messages.count()

    @admin.display(description="Processing time")
    def processing_time(self):
        ptime = timedelta(0)
        req_time = None
        for msg in self.messages.all():
            msg_spec = MessageSpec.model_validate(msg)
            if msg_spec.kind == MessageKindChoices.REQUEST:
                req_time = cast(ModelRequest, msg_spec.payload).timestamp
            if msg_spec.kind == MessageKindChoices.RESPONSE and req_time:
                ptime += cast(ModelResponse, msg_spec.payload).timestamp - req_time

        return f"{ptime.total_seconds():.2f}s"

    @admin.display(description="Collaborators")
    def collaborators_csv(self):
        return ", ".join([str(c) for c in self.collaborators.all()]) or None

    @admin.display(description="Status")
    def status(self):
        message = self.messages.latest("timestamp")
        context = {
            "kind": message.kind,
            "display_name": message.get_kind_display(),  # pyright: ignore[reportAttributeAccessIssue]
        }
        html_string = render_to_string("templates/status_badge.html", context)

        return mark_safe(html_string)


class SharedSession(Session):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Session"
        verbose_name_plural = "Shared Sessions"


class Message(MessageModel):
    @final
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    @override
    def __str__(self):
        return f"[{self.role}]: " + truncate_content(self.content, 55)

    @cached_property
    def spec(self):
        return MessageSpec.model_validate(self)

    @cached_property
    def agent_spec(self) -> AgentSpec:
        return trail_cache.get_sync(AgentSpec, self.agent.pk)

    @cached_property
    def session_link(self):
        url = reverse("admin:orm_session_change", args=[self.session.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            Session.objects.get(pk=self.session.pk),
        )

    @cached_property
    def agent_link(self):
        # agent_branch_id/agent_branch_name are annotated onto the queryset by
        # get_step_nav() (see django/portal/admin/utils.py); they aren't real
        # model fields, so django-types can't see them.
        if self.agent_branch_id:  # pyright: ignore[reportAttributeAccessIssue]
            url = (
                reverse(
                    "admin:orm_superagent_change",
                    args=[self.agent_branch_id],  # pyright: ignore[reportAttributeAccessIssue]
                )
                + f"?from_message={self.pk}"
            )
            label = f"{self.agent_branch_name} ({self.agent.fingerprint[:6]})"  # pyright: ignore[reportAttributeAccessIssue]
        else:
            url = (
                reverse("admin:orm_superagent_add")
            ) + f"?from_message={self.pk}&agent_fingerprint={self.agent.fingerprint}"
            label = self.agent.fingerprint[:6]

        return format_html('<a href="{}">{}</a>', url, label)

    @cached_property
    def link(self):
        url = reverse(
            "admin:orm_message_change",
            args=[self.pk],
        )
        label = f"#{self.pk}"

        return format_html('<a href="{}">{}</a>', url, label)

    @cached_property
    def output_schema(self):
        return self.agent_spec.output_type.definition

    @cached_property
    def tokens(self):
        if "usage" in self.payload:
            return (
                self.payload["usage"]["input_tokens"]
                + self.payload["usage"]["output_tokens"]
            )

    @cached_property
    def direction(self):
        return {
            MessageKindChoices.REQUEST: "sent",
            MessageKindChoices.RESPONSE: "received",
            MessageKindChoices.PROMPT: "init",
            MessageKindChoices.ERROR: "error",
        }[self.spec.kind]

    @cached_property
    def parts(self):
        if isinstance(self.spec.payload, ModelResponse):
            return len(self.spec.payload.parts)

    @cached_property
    def thinking(self):
        if isinstance(self.spec.payload, ModelResponse):
            part_content = get_part_content(self.spec.payload.parts, ThinkingPart)
            return part_content

    @cached_property
    def typed_content(self):
        if self.content is None:
            return None

        if self.output_schema and self.role == RoleChoices.ASSISTANT.value:
            data = json.loads(self.content)
            jsonschema.validate(
                instance=data,
                schema=self.output_schema,
            )
            return data
        else:
            return self.content

    @cached_property
    def content(self):
        # spec.kind determines the concrete type of spec.payload, but that
        # correlation isn't expressed in MessageSpec's type (payload is a
        # plain union); cast to the type this branch's kind guarantees.
        match self.spec.kind:
            case MessageKindChoices.PROMPT:
                return cast(PromptPayload, self.spec.payload).content
            case MessageKindChoices.ERROR:
                return cast(ErrorPayload, self.spec.payload).content
            case MessageKindChoices.REQUEST:
                request = cast(ModelRequest, self.spec.payload)
                match self.spec.role:
                    case RoleChoices.USER:
                        part_content = get_part_content(
                            request.parts,
                            UserPromptPart,
                        )
                    case RoleChoices.TOOL:
                        part_content = "[tool return]: " + truncate_content(
                            get_part_content(
                                request.parts,
                                ToolReturnPart,
                            ),
                            20,
                        )
                    case _:
                        raise NotImplementedError(f"unhandled value '{self.spec.role}'")

            case MessageKindChoices.RESPONSE:
                response = cast(ModelResponse, self.spec.payload)
                match self.spec.role:
                    case RoleChoices.ASSISTANT:
                        part_text = get_part_content(
                            response.parts,
                            TextPart,
                        )

                        part_tool_call = truncate_content(
                            get_part_content(
                                response.parts,
                                ToolCallPart,
                            ),
                            20,
                        )

                        if part_text and part_tool_call:
                            raise NotImplementedError(
                                "unhandled combo part with both text and tool call"
                            )

                        if part_tool_call:
                            part_content = f"[tool call]: {part_tool_call}"
                        else:
                            part_content = part_text

                    case _:
                        raise NotImplementedError(f"unhandled value '{self.spec.role}'")

        return part_content
