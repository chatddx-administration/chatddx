"""
A run written down: the trial it was a go at, the run with what came of it,
and the session its messages were exchanged in.
"""

import asyncio
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from django.utils import timezone
from pydantic_ai import AgentRunResultEvent, UsageLimitExceeded

from chatddx.core.utils import ensure_identity
from chatddx.dx.fake_vllm import ANSWER, FakeTransport, stream
from chatddx.history.models import (
    RunModel,
    RunStatus,
    RunToolBranchModel,
    TrialModel,
)
from chatddx.history.record import Branches, Outcome, record
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.configuration.pydantic import (
    ConfigurationBranchOut,
    ConfigurationTrailIn,
)
from chatddx.repo.entities.llm.pydantic import LLMBranchOut
from chatddx.repo.entities.reasoning.pydantic import ReasoningBranchOut
from chatddx.repo.entities.stack.pydantic import StackBranchOut
from chatddx.repo.entities.tool.pydantic import ToolBranchOut
from chatddx.repo.entity_names import EntityName
from chatddx.repo.store.branch import get_visible_branch_model
from chatddx.runtime import tools
from chatddx.runtime.implementation import blob_of
from chatddx.runtime.resolution import resolve
from chatddx.runtime.trial import TOOL_ROUNDS, Trial

pytestmark = pytest.mark.django_db

STACK = "qwen3-8b-awq@fake"

SLICES = ("instruction", "output", "coercion", "reasoning", "sampling", "toolset")


@pytest.fixture(autouse=True)
def provisioned(provision: Callable[..., None]) -> None:
    provision()


def branch(
    entity: EntityName, name: str | None = None, trail: int | None = None
) -> Any:
    return get_visible_branch_model(entity, "alex", name, trail=trail)


async def outcome_of(trial: Trial) -> Outcome:
    try:
        async with trial.stream() as events:
            async for event in events:
                if isinstance(event, AgentRunResultEvent):
                    return Outcome(RunStatus.COMPLETED, output=event.result.output)
    except UsageLimitExceeded as e:
        return Outcome(RunStatus.COMPLETED, error=str(e))

    raise AssertionError("the run ended with no result")


def written(
    configuration: str = "free-text",
    seed: int | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
    reasoning: str | None = None,
    user: str = "alex",
) -> RunModel:
    """
    A run of `configuration`, with `reasoning` set in it if given, on case-1,
    written down as `user`'s.
    """
    own = ConfigurationBranchOut.model_validate(branch("configuration", configuration))
    slices: dict[str, Any] = {entity: getattr(own.trail, entity) for entity in SLICES}

    if reasoning is not None:
        slices["reasoning"] = ReasoningBranchOut.model_validate(
            branch("reasoning", reasoning)
        ).trail

    cell = ConfigurationTrailIn.model_validate(slices, from_attributes=True)

    stack = StackBranchOut.model_validate(branch("stack", STACK))
    llm = branch("llm", trail=stack.trail.llm.id)
    facts = LLMBranchOut.model_validate(llm).details.facts
    toolset = own.trail.toolset
    tools = [
        ToolBranchOut.model_validate(branch("tool", trail=tool.id))
        for tool in (toolset.tools if toolset else [])
    ]
    case = branch("case", "case-1")

    trial = Trial(
        resolve(cell, stack.details, facts, stack.trail.serving),
        case.trail.vignette,
        transport=transport or FakeTransport(),
        seed=seed,
        implementations={
            tool.trail.name: tool.details.implementation.function
            for tool in tools
            if tool.details.implementation
        },
    )
    started = timezone.now()
    outcome = asyncio.run(outcome_of(trial))

    return record(
        user,
        cell,
        Branches(
            stack.id,
            llm.pk,
            {tool.id: trial.implementations[tool.trail.name].blob for tool in tools},
        ),
        case.trail_id,
        trial,
        outcome,
        started,
        timezone.now(),
        description="a run",
    )


def test_a_run_is_written_down_with_its_trial_session_and_messages():
    run = written(seed=7)

    assert run.status == RunStatus.COMPLETED
    assert (run.output, run.valid, run.finish_reason, run.error) == (
        ANSWER,
        None,
        "stop",
        None,
    )
    [request] = run.requests
    [response] = run.responses
    assert json.loads(request)["seed"] == 7
    assert response.endswith("data: [DONE]\n\n")
    assert run.started is not None and run.finished is not None
    assert run.started <= run.finished

    stack = branch("stack", STACK)
    trial = run.trial
    assert (trial.configuration_id, trial.stack_id, trial.case_id, trial.seed) == (
        branch("configuration", "free-text").trail_id,
        stack.trail_id,
        branch("case", "case-1").trail_id,
        7,
    )
    assert run.stack_branch_id == stack.pk
    assert run.llm_branch == branch("llm", "qwen3-8b-awq")

    assert run.client_id == branch("client", "chatddx-dev").trail_id
    assert run.client_rev is not None
    assert run.client_packages["pydantic-ai-slim"]

    assert run.session is not None
    messages = list(run.session.messages.all())
    assert [(m.kind, m.role) for m in messages] == [
        ("request", "user"),
        ("response", "assistant"),
    ]
    assert {m.run_id for m in messages} == {run.uuid}
    assert {m.payload["conversation_id"] for m in messages} == {str(run.session.uuid)}
    assert (run.session.context, run.session.description) == ("repl", "a run")


def test_the_same_cell_case_and_seed_is_another_run_of_one_trial():
    first = written(seed=7)
    again = written(seed=7)
    other = written(seed=8)

    assert first.trial_id == again.trial_id != other.trial_id
    assert first.uuid != again.uuid
    assert TrialModel.objects.count() == 2


def test_a_trial_is_no_one_s_and_each_run_its_maker_s():
    _ = ensure_identity("bob")
    alex = written()
    bob = written(user="bob")

    assert alex.trial_id == bob.trial_id
    assert (alex.owner.name, bob.owner.name) == ("alex", "bob")
    assert alex.trial.seed is None
    assert TrialModel.objects.count() == 1


def test_a_variation_set_in_a_cell_runs_a_configuration_with_no_branch():
    run = written(reasoning="off")

    configuration = run.trial.configuration
    assert configuration.reasoning_id == branch("reasoning", "off").trail_id
    assert not ConfigurationBranchModel.objects.filter(trail=configuration).exists()


def test_a_run_keeps_its_tools_branches_and_every_round():
    run = written("test-tools")

    assert sorted(tool.name for tool in run.tool_branches.all()) == [
        "sentinel_op",
        "sentinel_string",
    ]
    assert {
        row.tool_branch.name: row.blob
        for row in RunToolBranchModel.objects.filter(run=run)
    } == {
        name: blob_of(Path(tools.__file__).parent.joinpath(f"{name}.py").read_bytes())
        for name in ("sentinel_op", "sentinel_string")
    }
    assert len(run.requests) == len(run.responses) == 3
    assert [m.role for m in run.session.messages.all()] == [  # pyright: ignore[reportOptionalMemberAccess]
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
    ]


def test_a_run_that_came_to_no_answer_keeps_its_exchange_as_far_as_it_got():
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        text = "".join(stream(body | {"messages": body["messages"][:1]}))
        return httpx2.Response(
            200, headers={"content-type": "text/event-stream"}, content=text.encode()
        )

    run = written("test-tools", transport=httpx2.MockTransport(handler))

    assert (run.output, run.finish_reason) == (None, "tool_call")
    assert run.error is not None
    assert len(run.requests) == len(run.responses) == TOOL_ROUNDS + 1

    assert run.session is not None
    messages = list(run.session.messages.all())
    assert len(messages) == 2 * (TOOL_ROUNDS + 1) + 2
    assert [m.kind for m in messages[-2:]] == ["request", "error"]
    assert messages[-1].payload == {"error": run.error}
    assert messages[-1].run_id == run.uuid


def test_a_run_s_uuid_is_the_one_pydantic_ai_ran_under():
    run = written()

    assert run.session is not None
    [request, _] = run.session.messages.all()
    assert uuid.UUID(request.payload["run_id"]) == run.uuid
