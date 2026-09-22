# pyright: basic

import json
from datetime import timedelta
from functools import cached_property
from typing import NamedTuple, cast

import jsonschema
from django.contrib import admin
from django.db.models import Model
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from pydantic_ai import (
    ModelRequest,
    ModelResponse,
    NativeToolCallPart,
    NativeToolReturnPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from chatddx.core.choices import MessageKindChoices, RoleChoices
from chatddx.django.orm.annotations import BranchRef
from chatddx.django.portal.links import change_link
from chatddx.history.models import (
    BatchModel,
    ExperimentModel,
    MessageModel,
    RunModel,
    SessionModel,
)
from chatddx.history.schemas import ErrorPayload, MessageSpec, PromptPayload
from chatddx.repo.entities.agent.pydantic import AgentTrailSpec
from chatddx.repo.entities.case.django import Case
from chatddx.repo.entities.expect.django import Expect
from chatddx.repo.entities.super_agent.django import SuperAgent
from chatddx.repo.trail_cache import trail_cache
from chatddx.runtime.utils import get_part_content
from chatddx.utils import render_json_html, truncate_content

ALL_SCORERS = "All scorers"


class ToolCallSummary(NamedTuple):
    tool_name: str
    args_json: str


class ToolReturnSummary(NamedTuple):
    tool_name: str
    content: str


def as_proxy[T: Model](proxy: type[T], instance: Model) -> T:
    fields = instance._meta.concrete_fields  # pyright: ignore[reportAttributeAccessIssue]

    return proxy.from_db(
        instance._state.db,
        [f.attname for f in fields],
        [getattr(instance, f.attname) for f in fields],
    )


class Batch(BatchModel):
    agent_branch = BranchRef("agent", "agent", SuperAgent)

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Batch"
        verbose_name_plural = "Batches"

    def __str__(self):
        timestamp = self.timestamp.strftime("%Y-%m-%d %H:%M")
        return f"{timestamp} — {str(self.uuid)[:8]}"

    @cached_property
    def agent_link(self):
        return self.agent_branch.link()

    @admin.display(description="Case tags")
    def case_tags_csv(self):
        return ", ".join(str(tag) for tag in self.case_tags.all()) or None

    @admin.display(description="Scorers")
    def scorers_csv(self):
        return ", ".join(scorer.name for scorer in self.scorers.all()) or ALL_SCORERS

    @admin.display(description="Experiments")
    def experiment_count(self):
        return self.experiments.count()


class Experiment(ExperimentModel):
    agent_branch = BranchRef("agent", "agent", SuperAgent)
    case_branch = BranchRef("case", "case", Case)
    expect_branch = BranchRef("expect", "expect", Expect)

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Experiment"
        verbose_name_plural = "Experiments"

    def __str__(self):
        timestamp = self.timestamp.strftime("%Y-%m-%d %H:%M")
        return f"{timestamp} — {str(self.uuid)[:8]}"

    @admin.display(description="Collaborators")
    def collaborators_csv(self):
        return ", ".join(str(c) for c in self.collaborators.all()) or None

    @cached_property
    def agent_link(self):
        return self.agent_branch.link()

    @cached_property
    def case_link(self):
        return self.case_branch.link()

    @cached_property
    def batch_link(self):
        if not self.batch_id:
            return None

        assert self.batch is not None

        return change_link(as_proxy(Batch, self.batch))

    @cached_property
    def expect_label(self):
        return str(self.expect_branch.label)


class SharedExperiment(Experiment):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Experiment"
        verbose_name_plural = "Shared Experiments"


class Run(RunModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Run"
        verbose_name_plural = "Runs"

    def __str__(self):
        return f"[{self.uuid}]"

    @admin.display(description="Collaborators")
    def collaborators_csv(self):
        return ", ".join(str(c) for c in self.collaborators.all()) or None

    @cached_property
    def experiment_link(self):
        return change_link(as_proxy(Experiment, self.experiment))

    @cached_property
    def session_link(self):
        if not self.session_id:
            return None

        assert self.session is not None

        return change_link(as_proxy(Session, self.session))

    @cached_property
    def result_html(self):
        return render_json_html(self.result)


class SharedRun(Run):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Run"
        verbose_name_plural = "Shared Runs"


class Session(SessionModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Session"
        verbose_name_plural = "Sessions"

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
    agent_branch = BranchRef("agent", "agent", SuperAgent)

    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    def __str__(self):
        return f"[{self.role}]: " + truncate_content(self.content, 55)

    @cached_property
    def spec(self):
        return MessageSpec.model_validate(self)

    @cached_property
    def agent_spec(self) -> AgentTrailSpec:
        return trail_cache.get_sync(AgentTrailSpec, self.agent.pk)

    @cached_property
    def session_link(self):
        return change_link(as_proxy(Session, self.session))

    @cached_property
    def run_link(self):
        run = Run.objects.filter(uuid=self.run_id).first()

        if run is None:
            return self.run_id

        return change_link(run)

    @cached_property
    def agent_link(self):
        return self.agent_branch.link(from_message=self.pk)

    @cached_property
    def link(self):
        # A permalink to this very message, shown beside the content it
        # points at, so it reads as a number rather than repeating itself.
        return change_link(self, f"#{self.pk}")

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
    def tool_call(self) -> ToolCallSummary | None:
        if not isinstance(self.spec.payload, ModelResponse):
            return None

        for part in self.spec.payload.parts:
            if isinstance(part, (ToolCallPart, NativeToolCallPart)):
                return ToolCallSummary(
                    tool_name=part.tool_name,
                    args_json=json.dumps(part.args_as_dict(), indent=4),
                )

        return None

    @cached_property
    def tool_return(self) -> ToolReturnSummary | None:
        if not isinstance(self.spec.payload, ModelRequest):
            return None

        for part in self.spec.payload.parts:
            if isinstance(part, (ToolReturnPart, NativeToolReturnPart)):
                match part.content:
                    case str() as text:
                        content = text
                    case _:
                        content = json.dumps(part.content, indent=4)
                return ToolReturnSummary(tool_name=part.tool_name, content=content)

        return None

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
                        part_content = None
                    case _:
                        raise NotImplementedError(f"unhandled value '{self.spec.role}'")

            case MessageKindChoices.RESPONSE:
                response = cast(ModelResponse, self.spec.payload)
                match self.spec.role:
                    case RoleChoices.ASSISTANT:
                        part_content = get_part_content(
                            response.parts,
                            TextPart,
                        )

                    case _:
                        raise NotImplementedError(f"unhandled value '{self.spec.role}'")

        return part_content
