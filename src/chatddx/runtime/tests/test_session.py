"""A session holds a conversation, and a run can take it up where it was left."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from django.utils import timezone
from pydantic_ai import AgentRunResult, ModelMessagesTypeAdapter

from chatddx.dx.fake_vllm import ANSWER, FakeTransport
from chatddx.history.models import RunModel, RunStatus, SessionModel
from chatddx.history.record import Branches, Outcome, record
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.store.branch import get_visible_branch_model
from chatddx.runtime.resolution import Resolution
from chatddx.runtime.trial import Trial

type Cell = Callable[..., Resolution]
type Ran = Callable[[Trial], Coroutine[Any, Any, AgentRunResult[Any]]]

pytestmark = pytest.mark.django_db

STACK = "qwen3-8b-awq@fake"


def test_session(
    provision: Callable[..., None],
    cell: Cell,
    ran: Ran,
    test_inventory: ParsedInventory,
):
    provision()
    configuration, _ = test_inventory.configuration["baseline"]
    stack = get_visible_branch_model("stack", "alex", STACK)
    llm = get_visible_branch_model("llm", "alex", trail=stack.trail.llm_id)
    fake = FakeTransport()

    def run(case_name: str, session: SessionModel | None = None) -> RunModel:
        case = get_visible_branch_model("case", "alex", case_name)
        history = ModelMessagesTypeAdapter.validate_python(
            [message.payload for message in session.messages.all()] if session else []
        )
        trial = Trial(
            cell("baseline", STACK),
            case.trail.vignette,
            transport=fake,
            history=history,
            conversation_id=str(session.uuid) if session else None,
        )
        started = timezone.now()
        result = asyncio.run(ran(trial))

        return record(
            "alex",
            configuration,
            Branches(stack.pk, llm.pk),
            case.trail_id,
            trial,
            Outcome(RunStatus.COMPLETED, output=result.output),
            started,
            timezone.now(),
            session=session,
        )

    first = run("case-1")
    assert first.output == ANSWER
    assert first.session is not None

    again = run("case-2", session=first.session)

    assert again.session_id == first.session_id
    assert [m["role"] for m in fake.requests[1]["messages"]] == [
        "user",
        "assistant",
        "user",
    ]
    assert fake.requests[1]["messages"][-1]["content"] == "case vignette 2"
    assert [m.run_id for m in first.session.messages.all()] == [
        first.uuid,
        first.uuid,
        again.uuid,
        again.uuid,
    ]
