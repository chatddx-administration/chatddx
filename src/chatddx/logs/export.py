# pyright: basic
"""
An identity's runs of a cell as an inspect eval log (new-datamodel.md §4):
a sample per draw of a case, holding what the LLM was sent, the exchange,
the answer, and a model event per request with the bodies as they went and
came. Its metadata holds what inspect has no place for: the cell's
variation of each slice, the stack and its parts, the ids and fingerprints
that name what ran, the views the output offers as they read the answer,
and the case's targets, as whoever exports is held to them.

A seeded trial is one draw: its latest run that completed stands for it,
or its latest run where none did. Its epoch is its seed's place among the
seeds the log holds, from 1, so that an epoch is one seed across cases, as
a batch's replicate is. A trial with no seed makes a draw of each of its
runs, the epochs after the seeded ones, in the order they ran.

A sample is the case, by the name whoever exports sees it by, and by its
short fingerprint where it has none, or where the name is another case's
too. An errored run's sample carries its error, as inspect's own do.
"""

import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from django.utils import timezone
from inspect_ai import __version__ as INSPECT_VERSION
from inspect_ai.event import Event, ModelEvent
from inspect_ai.log import (
    EvalConfig,
    EvalDataset,
    EvalError,
    EvalLog,
    EvalPlan,
    EvalPlanStep,
    EvalResults,
    EvalSample,
    EvalSpec,
    EvalStats,
    write_eval_log,
)
from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    GenerateConfig,
    ModelCall,
)
from pydantic import JsonValue
from pydantic_ai import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
)

from chatddx.history.models import (
    MessageKind,
    MessageModel,
    RunModel,
    RunStatus,
    RunToolBranchModel,
)
from chatddx.logs.messages import (
    body,
    chat_messages,
    generate_config,
    output,
    usage,
)
from chatddx.repl.cell import NONE, SLICES
from chatddx.repo.entities.case.pydantic import pattern_of
from chatddx.repo.entities.configuration.django import ConfigurationTrailModel
from chatddx.repo.entities.output.pydantic import VIEWS, OutputTrailOut
from chatddx.repo.entities.stack.django import StackTrailModel
from chatddx.repo.entity_names import EntityName
from chatddx.repo.names import short_fingerprint
from chatddx.repo.store.branch import (
    AmbiguousBranchError,
    BranchNotFoundError,
    get_visible_branch_model,
)
from chatddx.repo.store.trail import load_trail
from chatddx.scoring.score import Scoring

STACK_PARTS: tuple[EntityName, ...] = ("machine", "os", "llm", "serving")

# the target a sample holds: what the diagnosis scorers read
TARGET_KIND = "diagnosis"


def cell_log(
    identity: str,
    configuration: ConfigurationTrailModel,
    stack: StackTrailModel,
    task: str,
) -> EvalLog:
    """
    `identity`'s runs of the configuration on the stack, as the log of a
    task called `task`.
    """
    runs = list(
        RunModel.objects.filter(
            owner__name=identity,
            trial__configuration=configuration,
            trial__stack=stack,
        )
        .select_related("trial__case", "stack_branch", "client", "conversation")
        .order_by("timestamp", "pk")
    )
    names = _Names(identity)
    scoring = Scoring(identity)
    offered = cast(
        OutputTrailOut,
        load_trail("output", configuration.output.fingerprint, OutputTrailOut),
    )
    draws = _draws(runs)
    cases = _case_ids(names, [run.trial.case for run, _ in draws])
    served = _served(runs)
    stack_name = names.of("stack", stack)
    model = f"vllm/{stack_name}"
    cell = {
        "cell": task,
        **{
            entity: names.of(entity, getattr(configuration, entity))
            for entity in SLICES
        },
        "stack": stack_name,
        **{entity: names.of(entity, getattr(stack, entity)) for entity in STACK_PARTS},
    }
    samples = sorted(
        (
            _sample(
                run,
                cases[run.trial.case_id],
                epoch,
                cell,
                names,
                scoring,
                model,
                served,
            )
            for run, epoch in draws
        ),
        key=lambda sample: (str(sample.id), sample.epoch),
    )
    created = timezone.now()
    config = generate_config(runs[0].requests[0]) if runs and runs[0].requests else None

    spec = EvalSpec(
        eval_id=_short_id(),
        run_id=_short_id(),
        created=created.isoformat(),
        task=task,
        task_id=_short_id(),
        task_version=0,
        dataset=EvalDataset(
            name="cases",
            samples=len(set(cases.values())),
            sample_ids=sorted(set(cases.values())),
        ),
        model=model,
        model_generate_config=(
            config.model_copy(update={"seed": None}) if config else GenerateConfig()
        ),
        model_base_url=_endpoint(runs),
        config=EvalConfig(epochs=max((sample.epoch for sample in samples), default=1)),
        packages={
            **(runs[-1].client_packages if runs else {}),
            "inspect_ai": INSPECT_VERSION,
        },
        metadata={
            "identity": identity,
            **cell,
            "views": [view for view in VIEWS if view in offered.views],
            "fingerprints": {
                "configuration": configuration.fingerprint,
                "stack": stack.fingerprint,
            },
        },
    )
    used = [
        sample.model_usage[model] for sample in samples if model in sample.model_usage
    ]

    return EvalLog(
        status="success",
        eval=spec,
        plan=EvalPlan(
            name="chatddx",
            steps=[EvalPlanStep(solver="chatddx", params={"cell": task})],
        ),
        results=EvalResults(
            total_samples=len(samples),
            completed_samples=sum(sample.error is None for sample in samples),
        ),
        stats=EvalStats(
            started_at=_moment(
                min((run.started for run, _ in draws if run.started), default=None)
            ),
            completed_at=_moment(
                max((run.finished for run, _ in draws if run.finished), default=None)
            ),
            model_usage={model: sum(used[1:], used[0])} if used else {},
        ),
        samples=samples,
    )


def write(log: EvalLog, directory: str | Path | None = None) -> Path:
    """
    Write `log` into `directory`, or where inspect looks for logs, named as
    inspect names its own.
    """
    where = Path(directory or os.environ.get("INSPECT_LOG_DIR") or "logs")
    where.mkdir(parents=True, exist_ok=True)
    created = datetime.fromisoformat(log.eval.created)
    stamp = created.strftime("%Y-%m-%dT%H-%M-%S%z")
    task = re.sub(r"[^\w.@=+-]+", "-", log.eval.task).strip("-")
    path = where / f"{stamp}_{task}_{log.eval.eval_id}.eval"
    write_eval_log(log, path)

    return path


class _Names:
    """What the identity calls each trail, or its short fingerprint."""

    def __init__(self, identity: str):
        self.identity: str = identity
        self._names: dict[tuple[EntityName, int], str] = {}

    def of(self, entity: EntityName, trail: Any) -> str:
        if trail is None:
            return NONE

        key = (entity, trail.pk)

        if key not in self._names:
            try:
                self._names[key] = get_visible_branch_model(
                    entity, self.identity, trail=trail.pk
                ).name
            except (BranchNotFoundError, AmbiguousBranchError):
                self._names[key] = short_fingerprint(trail.fingerprint)

        return self._names[key]


def _draws(runs: list[RunModel]) -> list[tuple[RunModel, int]]:
    """Each draw, by the run that stands for it, and its epoch."""
    by_trial: dict[int, list[RunModel]] = defaultdict(list)

    for run in runs:
        by_trial[run.trial_id].append(run)

    seeds = sorted({run.trial.seed for run in runs if run.trial.seed is not None})
    unseeded: dict[int, int] = defaultdict(int)
    draws: list[tuple[RunModel, int]] = []

    for trial_runs in by_trial.values():
        seed = trial_runs[0].trial.seed

        if seed is not None:
            completed = [run for run in trial_runs if run.status == RunStatus.COMPLETED]
            draws.append(((completed or trial_runs)[-1], seeds.index(seed) + 1))
            continue

        for run in trial_runs:
            unseeded[run.trial.case_id] += 1
            draws.append((run, len(seeds) + unseeded[run.trial.case_id]))

    return draws


def _case_ids(names: _Names, cases: list[Any]) -> dict[int, str]:
    """Each case's sample id: its name, or its short fingerprint."""
    named = {case.pk: names.of("case", case) for case in cases}
    counts: dict[str, int] = defaultdict(int)

    for name in named.values():
        counts[name] += 1

    fingerprints = {case.pk: short_fingerprint(case.fingerprint) for case in cases}

    return {
        pk: name if counts[name] == 1 else f"{name}@{fingerprints[pk]}"
        for pk, name in named.items()
    }


def _sample(
    run: RunModel,
    case_id: str,
    epoch: int,
    cell: dict[str, str],
    names: _Names,
    scoring: Scoring,
    model: str,
    served: str,
) -> EvalSample:
    history, added = _stored(run)
    messages = chat_messages(history + added)
    responses = [message for message in added if isinstance(message, ModelResponse)]
    answers = [
        i
        for i, message in enumerate(messages)
        if isinstance(message, ChatMessageAssistant)
        and i >= len(chat_messages(history))
    ]
    case = scoring.case_of(run)
    targets: dict[str, JsonValue] = case.details.get("targets", {}) if case else {}
    target = pattern_of(targets.get(TARGET_KIND))
    the_output = scoring.output_of(run)
    answered = output(served, responses[-1] if responses else None)
    answered.completion = _completion(the_output, run.answer) or answered.completion
    answered.usage = usage(responses)

    return EvalSample(
        id=case_id,
        epoch=epoch,
        input=messages[: answers[0] if answers else len(messages)] or "",
        target=target or "",
        messages=messages,
        output=answered,
        metadata={
            **cell,
            "case": names.of("case", run.trial.case),
            "language": case.details.get("language") if case else None,
            "seed": run.trial.seed,
            "trial": str(run.trial.uuid),
            "run": str(run.uuid),
            "status": run.status,
            "valid": run.valid,
            "finish_reason": run.finish_reason,
            "error": run.error,
            "answer": run.answer,
            "views": _views(the_output, run.answer),
            "targets": targets,
            "fingerprints": {
                "configuration": run.trial.configuration.fingerprint,
                "stack": run.trial.stack.fingerprint,
                "case": run.trial.case.fingerprint,
                "output": the_output.fingerprint,
            },
            "client": {
                "build": run.client.build if run.client else None,
                "rev": run.client_rev,
            },
            "tools": {
                link.tool_branch.name: link.blob
                for link in RunToolBranchModel.objects.filter(run=run).select_related(
                    "tool_branch"
                )
            },
        },
        events=_events(run, added, messages, answers, model, served),
        model_usage={model: answered.usage} if answered.usage else {},
        started_at=run.started.isoformat() if run.started else None,
        completed_at=run.finished.isoformat() if run.finished else None,
        total_time=_seconds(run),
        working_time=_seconds(run),
        uuid=str(run.uuid),
        error=(
            EvalError(message=run.error or "errored", traceback="", traceback_ansi="")
            if run.status == RunStatus.ERRORED
            else None
        ),
    )


def _stored(run: RunModel) -> tuple[list[ModelMessage], list[ModelMessage]]:
    """The conversation the run continued, if any, and what the run added to it."""
    if run.conversation is None:
        return [], []

    stored = list(run.conversation.messages.exclude(kind=MessageKind.ERROR))
    own = [i for i, message in enumerate(stored) if message.run_uuid == run.uuid]

    if not own:
        return [], []

    def read(part: list[MessageModel]) -> list[ModelMessage]:
        return ModelMessagesTypeAdapter.validate_python([m.payload for m in part])

    return read(stored[: own[0]]), read(stored[own[0] : own[-1] + 1])


def _events(
    run: RunModel,
    added: list[ModelMessage],
    messages: list[ChatMessage],
    answers: list[int],
    model: str,
    served: str,
) -> list[Event]:
    """
    A model event per request the run sent, with the bodies as they went
    and came, and what the LLM had been sent up to it: the messages before
    the answer the request got, its `answers`' place among `messages`.
    """
    requests = [m for m in added if isinstance(m, ModelRequest)]
    responses = [m for m in added if isinstance(m, ModelResponse)]
    events: list[Event] = []

    for i, sent in enumerate(run.requests):
        response = responses[i] if i < len(responses) else None
        received = run.responses[i] if i < len(run.responses) else None
        started = requests[i].timestamp if i < len(requests) else run.started

        events.append(
            ModelEvent(
                model=model,
                input=messages[: answers[i]] if i < len(answers) else messages,
                tools=[],
                tool_choice="auto",
                config=generate_config(sent),
                output=output(served, response),
                call=ModelCall(
                    request=body(sent),
                    response=body(received) if received is not None else None,
                ),
                timestamp=started or timezone.now(),
                completed=response.timestamp if response else run.finished,
                error=None if response else run.error,
            )
        )

    return events


def _views(
    output_trail: OutputTrailOut, answer: JsonValue
) -> dict[str, list[str]] | None:
    """What each view the output offers reads from the answer, as a scorer gets it."""
    if answer is None:
        return None

    return {
        view: [str(item) for item in output_trail.view(view, answer)]
        for view in VIEWS
        if view in output_trail.views
    }


def _completion(output_trail: OutputTrailOut, answer: JsonValue) -> str:
    """
    The answer as text: its `text` view where the output offers one, and a
    structured answer's JSON otherwise.
    """
    if answer is None:
        return ""

    if "text" in output_trail.views:
        return "\n\n".join(str(item) for item in output_trail.view("text", answer))

    if isinstance(answer, str):
        return answer

    return json.dumps(answer, ensure_ascii=False, indent=2)


def _served(runs: list[RunModel]) -> str:
    """The name the stack's LLM was served by, as the runs' stack rows say."""
    for run in reversed(runs):
        if run.stack_branch and run.stack_branch.details.get("served_name"):
            return cast(str, run.stack_branch.details["served_name"])

    return "unknown"


def _endpoint(runs: list[RunModel]) -> str | None:
    for run in reversed(runs):
        if run.stack_branch and run.stack_branch.details.get("endpoint"):
            return cast(str, run.stack_branch.details["endpoint"])

    return None


def _moment(moment: datetime | None) -> str:
    return moment.isoformat() if moment else ""


def _seconds(run: RunModel) -> float | None:
    if run.started and run.finished:
        return (run.finished - run.started).total_seconds()

    return None


def _short_id() -> str:
    return uuid.uuid4().hex[:22]
