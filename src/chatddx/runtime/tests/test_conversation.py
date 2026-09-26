import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from django.utils import timezone
from pydantic_ai import AgentRunResult, ModelMessagesTypeAdapter

from chatddx.dev.fake_vllm import ANSWER, FakeTransport
from chatddx.history.models import ConversationModel, RunModel, RunStatus
from chatddx.history.record import Branches, Outcome, record
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.store.branch import get_visible_branch_model
from chatddx.runtime.resolution import Resolution
from chatddx.runtime.run import Run

type Cell = Callable[..., Resolution]
type Ran = Callable[[Run], Coroutine[Any, Any, AgentRunResult[Any]]]

pytestmark = pytest.mark.django_db

STACK = "qwen3-8b-awq@fake"


def test_a_run_takes_a_conversation_up_where_it_was_left(
    cell: Cell,
    ran: Ran,
    test_inventory: ParsedInventory,
):
    configuration, _ = test_inventory.configuration["baseline"]
    stack = get_visible_branch_model("stack", "alice", STACK)
    llm = get_visible_branch_model("llm", "alice", trail=stack.trail.llm_id)
    fake = FakeTransport()

    def recorded(
        case_name: str, conversation: ConversationModel | None = None
    ) -> RunModel:
        case = get_visible_branch_model("case", "alice", case_name)
        history = ModelMessagesTypeAdapter.validate_python(
            [message.payload for message in conversation.messages.all()]
            if conversation
            else []
        )
        run = Run(
            cell("baseline", STACK),
            case.trail.vignette,
            transport=fake,
            history=history,
            conversation_id=str(conversation.uuid) if conversation else None,
        )
        started = timezone.now()
        result = asyncio.run(ran(run))

        return record(
            "alice",
            configuration,
            Branches(stack.pk, llm.pk),
            case.trail_id,
            run,
            Outcome(RunStatus.COMPLETED, answer=result.output),
            started,
            timezone.now(),
            conversation=conversation,
        )

    first = recorded("case-1")
    assert first.answer == ANSWER
    assert first.conversation is not None

    again = recorded("case-2", conversation=first.conversation)

    assert again.conversation_id == first.conversation_id
    assert [m["role"] for m in fake.requests[1]["messages"]] == [
        "user",
        "assistant",
        "user",
    ]
    assert fake.requests[1]["messages"][-1]["content"] == "case vignette 2"
    assert [m.run_uuid for m in first.conversation.messages.all()] == [
        first.uuid,
        first.uuid,
        again.uuid,
        again.uuid,
    ]
