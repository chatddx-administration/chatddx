import uuid

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from pydantic_ai import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_core import to_jsonable_python

from chatddx.core.choices import RoleChoices
from chatddx.history.models import MessageModel, SessionModel
from chatddx.repo.families.django import BranchModel
from chatddx.repo.inventories import InventoryBranchModel

pytestmark = [
    pytest.mark.django_db(transaction=True),
]


def _make_message(
    session: SessionModel,
    agent_branch: BranchModel,
    payload: ModelRequest | ModelResponse,
    role: RoleChoices = RoleChoices.ASSISTANT,
) -> MessageModel:
    return MessageModel.objects.create(
        agent_id=agent_branch.target.pk,
        session=session,
        kind=payload.kind,
        run_id=uuid.uuid4(),
        role=role,
        payload=to_jsonable_python(payload),
        timestamp=timezone.now(),
    )


def test_session_view_renders_thinking(
    session: SessionModel,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    response = ModelResponse(
        parts=[
            ThinkingPart(content="reasoning about the answer"),
            TextPart(content="the answer"),
        ]
    )
    agent_branch = inventory_fixture_bm["agent"]["agent-2"]
    _ = _make_message(session, agent_branch, response)

    admin_response = user_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "reasoning about the answer" in content


def test_session_view_omits_thinking_block_when_absent(
    session: SessionModel,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    response = ModelResponse(parts=[TextPart(content="the answer")])
    agent_branch = inventory_fixture_bm["agent"]["agent-2"]

    _ = _make_message(session, agent_branch, response)

    admin_response = user_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "the answer" in content
    assert "Thinking" not in content


def test_session_view_renders_tool_call(
    session: SessionModel,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    """A tool call is its own section, with the tool name in the summary and
    the full (untruncated) args rendered as JSON in the details."""
    response = ModelResponse(
        parts=[ToolCallPart(tool_name="sentinel_op", args={"a": 12, "b": 8})]
    )
    agent_branch = inventory_fixture_bm["agent"]["agent-2"]
    _ = _make_message(session, agent_branch, response)

    admin_response = user_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "Tool Call: sentinel_op" in content
    assert escape('"a": 12') in content
    assert escape('"b": 8') in content


def test_session_view_omits_tool_call_block_when_absent(
    session: SessionModel,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    response = ModelResponse(parts=[TextPart(content="the answer")])
    agent_branch = inventory_fixture_bm["agent"]["agent-2"]
    _ = _make_message(session, agent_branch, response)

    admin_response = user_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "Tool Call:" not in content


def test_session_view_renders_tool_return(
    session: SessionModel,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    """A tool return is its own section too, with the tool name in the
    summary and the full content rendered as JSON in the details."""
    request = ModelRequest(
        parts=[ToolReturnPart(tool_name="sentinel_op", content={"result": 20})]
    )
    agent_branch = inventory_fixture_bm["agent"]["agent-2"]
    _ = _make_message(session, agent_branch, request, role=RoleChoices.TOOL)

    admin_response = user_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "Tool Return: sentinel_op" in content
    assert escape('"result": 20') in content


def test_session_view_omits_tool_return_block_when_absent(
    session: SessionModel,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    response = ModelResponse(parts=[TextPart(content="the answer")])
    agent_branch = inventory_fixture_bm["agent"]["agent-2"]
    _ = _make_message(session, agent_branch, response)

    admin_response = user_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "Tool Return:" not in content


def test_session_view_does_not_render_literal_none_for_missing_content(
    session: SessionModel,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    """A tool-return-only message has no plain-text content -- the main
    content box must be omitted entirely rather than printing "None"."""
    request = ModelRequest(
        parts=[ToolReturnPart(tool_name="sentinel_op", content={"result": 20})]
    )
    agent_branch = inventory_fixture_bm["agent"]["agent-2"]
    _ = _make_message(session, agent_branch, request, role=RoleChoices.TOOL)

    admin_response = user_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert ">None<" not in content
