# pyright: basic
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _, ngettext

from chatddx.bench.bench import Bench
from chatddx.bench.cell import SLICES
from chatddx.django.portal.configurations import (
    page_of_run as configuration_page_of,
)
from chatddx.django.portal.models import BatchModel
from chatddx.django.portal.stacks import page_of_run
from chatddx.django.portal.status import value_of
from chatddx.history.models import (
    MessageKind,
    MessageModel,
    RunModel,
    RunStatus,
    RunToolModel,
    ScoreModel,
)
from chatddx.repo.entities.output.pydantic import VIEWS
from chatddx.runtime.run import FINAL_RESULT, invalid
from chatddx.scoring.score import Scoring
from chatddx.worker.models import JobModel

_FAILED = re.compile(r"^(invalid arguments: |[A-Z]\w*(Error|Exception): )")

PREVIEW = 120

ROLES: dict[str, Any] = {
    "system": _("System"),
    "user": _("User"),
    "assistant": _("Assistant"),
    "tool": _("Tools"),
    "unknown": _("Error"),
}


@dataclass(frozen=True)
class Detail:
    label: Any
    value: str
    trouble: bool = False
    link: str | None = None


@dataclass(frozen=True)
class Part:
    kind: str
    label: str
    text: str
    code: bool = False
    folded: bool = False
    trouble: bool = False
    note: str | None = None
    tool: str | None = None


@dataclass(frozen=True)
class Message:
    number: int
    role: str
    kind: str
    when: datetime
    said: str
    parts: list[Part]
    usage: str | None = None
    model: str | None = None
    finish: str | None = None
    trouble: bool = False

    @property
    def label(self) -> Any:
        return ROLES.get(self.role, self.role)


@dataclass(frozen=True)
class Score:
    scorer: str
    value: str
    answer: str | None
    reason: str | None
    target: str | None
    when: datetime
    latest: bool


@dataclass(frozen=True)
class Exchanged:
    number: int
    which: str
    size: str
    events: int | None = None


@dataclass(frozen=True)
class Shown:
    run: RunModel
    description: str
    outcome: str
    trouble: bool
    took: str | None
    details: list[Detail]
    slices: list[tuple[str, str]]
    configuration: str
    configuration_page: str | None
    answer: str | None
    views: list[tuple[str, list[str]]]
    unheld: str | None
    scores: list[Score]
    messages: list[Message]
    exchanged: list[Exchanged] = field(default_factory=list[Exchanged])


def shown(run: RunModel) -> Shown:
    owner = run.owner.name
    bench = Bench(owner)
    scoring = Scoring(owner)
    trial = run.trial
    output = scoring.output_of(run)
    outcome, trouble = outcome_of(run)
    stored = list(
        MessageModel.objects.filter(
            run_uuid=run.uuid, conversation=run.conversation
        ).order_by("pk")
    )
    responses = [
        message.payload for message in stored if message.kind == MessageKind.RESPONSE
    ]
    tokens_in = sum(_usage(payload, "input_tokens") for payload in responses)
    tokens_out = sum(_usage(payload, "output_tokens") for payload in responses)
    tools = RunToolModel.objects.filter(run=run).select_related("tool_branch")
    stack = run.stack_branch
    answer = run.answer
    held = scoring.case_of(run)
    job = JobModel.objects.filter(run=run).first()
    stack_page = page_of_run(run)

    details = [
        Detail(_("Why"), run.error, True) if run.error else None,
        Detail(_("Finish"), run.finish_reason) if run.finish_reason else None,
        Detail(
            _("Case"), bench.name_of("case", trial.case), link=_case_page(held, owner)
        ),
        Detail(_("Batch"), str(job.batch)[:8], link=_batch_page(owner, job.batch))
        if job is not None
        else None,
        Detail(
            _("Trial"),
            gettext("run %(number)d of %(runs)d of trial %(trial)s")
            % {
                "number": trial.runs.filter(pk__lte=run.pk).count(),
                "runs": trial.runs.count(),
                "trial": str(trial.uuid)[:8],
            },
        ),
        Detail(_("Seed"), "none" if trial.seed is None else f"#{trial.seed}"),
        Detail(
            _("Stack"),
            stack.name if stack is not None else bench.name_of("stack", trial.stack),
            link=stack_page,
        ),
        Detail(
            _("LLM"),
            run.llm_branch.name if run.llm_branch else bench.name_of("llm", None),
            link=f"{stack_page}#llm" if stack_page and run.llm_branch else None,
        ),
        Detail(_("Served as"), _served(stack)) if stack is not None else None,
        Detail(
            _("Tools"),
            ", ".join(f"{ran.tool_branch.name} (file {ran.blob[:7]})" for ran in tools),
        )
        if tools
        else None,
        Detail(_("Client"), _client(run)),
        Detail(
            _("Tokens"),
            ngettext(
                "%(sent)d in, %(written)d out, over %(requests)d request",
                "%(sent)d in, %(written)d out, over %(requests)d requests",
                len(run.requests),
            )
            % {
                "sent": tokens_in,
                "written": tokens_out,
                "requests": len(run.requests),
            },
        ),
        Detail(
            _("Conversation"),
            f"{run.conversation.context} {str(run.conversation.uuid)[:8]}"
            if run.conversation
            else "—",
        ),
    ]

    return Shown(
        run=run,
        description=description_of(run),
        outcome=outcome,
        trouble=trouble,
        took=_took(run.started, run.finished),
        details=[detail for detail in details if detail is not None],
        slices=[
            (entity, bench.name_of(entity, getattr(trial.configuration, entity)))
            for entity in SLICES
        ],
        configuration=description_of(run).split(" × ")[0],
        configuration_page=configuration_page_of(run, job),
        answer=None if answer is None else _written(answer),
        views=[
            (view, [str(item) for item in output.view(view, answer)])
            for view in VIEWS
            if view in output.views
        ]
        if answer is not None
        else [],
        unheld=invalid(output.answer_schema, answer)
        if answer is not None
        and output.answer_schema is not None
        and run.valid is False
        else None,
        scores=scores_of(run, scoring),
        messages=messages_of(stored),
        exchanged=exchanged_of(run),
    )


def outcome_of(run: RunModel) -> tuple[str, bool]:
    if run.status == RunStatus.ERRORED:
        return gettext("stopped" if run.error == "stopped" else "errored"), True

    match run.valid:
        case True:
            return gettext("valid"), bool(run.error)
        case False:
            return gettext("invalid"), True
        case _:
            return gettext("completed"), bool(run.error)


def scores_of(run: RunModel, scoring: Scoring) -> list[Score]:
    latest = {score.pk for score in scoring.latest(run)}
    made: list[ScoreModel] = [
        score for score in run.scores.all() if score.owner_id == scoring.owner_id
    ]

    return [
        Score(
            score.scorer_name,
            value_of(score.value),
            score.answer,
            score.reason,
            score.target,
            score.timestamp,
            score.pk in latest,
        )
        for score in sorted(made, key=lambda score: (score.pk not in latest, -score.pk))
    ]


def messages_of(stored: list[MessageModel]) -> list[Message]:
    found: list[Message] = []
    instructions: str | None = None

    for number, message in enumerate(stored, 1):
        given = message.payload.get("instructions")
        found.append(message_of(number, message, given != instructions))
        instructions = given if message.kind == MessageKind.REQUEST else instructions

    return found


def message_of(number: int, message: MessageModel, instructed: bool = True) -> Message:
    payload = message.payload

    if message.kind == MessageKind.ERROR:
        error = str(payload.get("error", ""))
        return Message(
            number,
            message.role,
            message.kind,
            message.timestamp,
            _preview(error),
            [Part("error", gettext("Error"), error, trouble=True)],
            trouble=True,
        )

    parts = parts_of(payload, instructed)
    sent, written = _usage(payload, "input_tokens"), _usage(payload, "output_tokens")

    return Message(
        number,
        message.role,
        message.kind,
        message.timestamp,
        _said(parts),
        parts,
        usage=gettext("%(sent)d in, %(written)d out")
        % {"sent": sent, "written": written}
        if sent or written
        else None,
        model=payload.get("model_name"),
        finish=payload.get("finish_reason"),
        trouble=any(part.trouble for part in parts),
    )


def parts_of(payload: dict[str, Any], instructed: bool = True) -> list[Part]:
    found: list[Part] = []

    if instructed and payload.get("kind") == "request" and payload.get("instructions"):
        found.append(
            Part("instructions", gettext("Instructions"), str(payload["instructions"]))
        )

    for part in payload.get("parts", []):
        found.append(_part(part))

    return found


def _part(part: dict[str, Any]) -> Part:
    kind = part.get("part_kind", "")
    content = part.get("content")

    match kind:
        case "system-prompt":
            return Part("system", gettext("System"), _text(content))
        case "user-prompt":
            return Part("user", gettext("User"), _text(content))
        case "instruction":
            return Part("instructions", gettext("Instructions"), _text(content))
        case "thinking":
            return Part("thinking", gettext("Thinking"), _text(content), folded=True)
        case "text":
            text = _text(content)
            written = _json(text)
            return Part(
                "text",
                gettext("Text"),
                text if written is None else written,
                code=written is not None,
            )
        case "tool-call":
            arguments = part.get("args")
            written = (
                _json(arguments) or arguments
                if isinstance(arguments, str)
                else json.dumps(arguments, indent=2, ensure_ascii=False)
            )
            return Part(
                "call",
                gettext("Calls %(tool)s") % {"tool": part.get("tool_name")},
                written,
                code=True,
                note=part.get("tool_call_id"),
                tool=part.get("tool_name"),
            )
        case "tool-return":
            text = _text(content)
            return Part(
                "return",
                gettext("%(tool)s returned") % {"tool": part.get("tool_name")},
                text,
                trouble=bool(_FAILED.match(text)),
                note=part.get("tool_call_id"),
                tool=part.get("tool_name"),
            )
        case "retry-prompt":
            return Part("retry", gettext("Asked again"), _text(content), trouble=True)
        case _:
            return Part(
                kind or "other",
                kind or gettext("Other"),
                json.dumps(part, indent=2, ensure_ascii=False),
                code=True,
            )


def exchanged_of(run: RunModel) -> list[Exchanged]:
    found: list[Exchanged] = []

    for number, request in enumerate(run.requests, 1):
        found.append(Exchanged(number, "request", _size(request)))

        if number <= len(run.responses):
            response = run.responses[number - 1]
            found.append(
                Exchanged(number, "response", _size(response), response.count("data: "))
            )

    return found


def exchange_of(run: RunModel, number: int, which: str) -> str | None:
    held = run.requests if which == "request" else run.responses

    if not 0 < number <= len(held):
        return None

    body = held[number - 1]

    if which == "request":
        written = _json(body)
        return body if written is None else written

    return body


def _case_page(case: Any, owner: str) -> str | None:
    if case is None or case.owner.name != owner:
        return None

    return reverse("admin:portal_case_change", args=[case.pk])


def _batch_page(owner: str, batch: Any) -> str | None:
    found = BatchModel.objects.filter(uuid=batch, owner__name=owner).first()

    return (
        None if found is None else reverse("admin:portal_batch_change", args=[found.pk])
    )


def description_of(run: RunModel) -> str:
    conversation = run.conversation

    if conversation is None or not conversation.description:
        return "—"

    return conversation.description


def _took(started: datetime | None, finished: datetime | None) -> str | None:
    if started is None or finished is None:
        return None

    seconds = (finished - started) / timedelta(seconds=1)
    minutes, rest = divmod(seconds, 60)

    return f"{int(minutes)} min {rest:.0f} s" if minutes else f"{seconds:.1f} s"


def _served(stack: Any) -> str:
    details: dict[str, Any] = stack.details
    served, endpoint = details.get("served_name"), details.get("endpoint")

    return " at ".join(str(part) for part in (served, endpoint) if part) or "—"


def _client(run: RunModel) -> str:
    if run.client is None:
        return gettext("none recorded")

    if run.client.build is not None:
        return str(run.client.build)

    rev = run.client_rev or ""

    return (
        gettext("a dev shell at %(rev)s") % {"rev": rev[:12]}
        if rev
        else gettext("a dev shell")
    )


def _usage(payload: dict[str, Any], count: str) -> int:
    usage = payload.get("usage") or {}
    value = usage.get(count)
    return value if isinstance(value, int) else 0


def _written(answer: Any) -> str:
    if isinstance(answer, str):
        return answer

    return json.dumps(answer, indent=2, ensure_ascii=False)


def _said(parts: list[Part]) -> str:
    said: list[str] = []

    for part in parts:
        match part.kind:
            case "user" | "system" | "retry" | "error":
                said.append(part.text)
            case "thinking":
                said.append(gettext("thinking"))
            case "text" if part.code:
                said.append(gettext("the answer"))
            case "text" if part.text.lstrip().startswith(("{", "[")):
                # a document it didn't get to the end of
                said.append(gettext("the answer, unfinished"))
            case "text":
                said.append(f"“{part.text}”")
            case "call":
                said.append(_asked(part))
            case "return":
                said.append(f"{part.tool} → {part.text}")
            case _:
                pass

    return _preview(" · ".join(said) or " · ".join(part.label for part in parts))


def _asked(call: Part) -> str:
    if call.tool == FINAL_RESULT:
        return gettext("%(tool)s: the answer") % {"tool": call.tool}

    try:
        arguments = json.loads(call.text)
    except ValueError:
        arguments = None

    first = (
        next((value for value in arguments.values() if isinstance(value, str)), None)
        if isinstance(arguments, dict)
        else None
    )

    return f"{call.tool}(“{first}”)" if first is not None else str(call.tool)


def _preview(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= PREVIEW else f"{line[: PREVIEW - 1]}…"


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "\n".join(
            item if isinstance(item, str) else json.dumps(item) for item in content
        )

    return json.dumps(content, indent=2, ensure_ascii=False)


def _json(text: str) -> str | None:
    stripped = text.strip()

    if not stripped.startswith(("{", "[")):
        return None

    try:
        return json.dumps(json.loads(stripped), indent=2, ensure_ascii=False)
    except ValueError:
        return None


def _size(body: str) -> str:
    size = len(body.encode())
    return f"{size / 1024:.1f} kB" if size >= 1024 else f"{size} B"
