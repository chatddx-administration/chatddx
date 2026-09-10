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

from chatddx.core.choices import RoleChoices, SessionContextChoices
from chatddx.core.models import IdentityModel
from chatddx.history.models import MessageModel, SessionModel
from chatddx.repo.base import BranchModel
from chatddx.repo.branch_models import BranchModelRegistry


def _by_name(branches: dict[int, BranchModel], name: str) -> BranchModel:
    return next(branch for branch in branches.values() if branch.name == name)


@pytest.fixture
def session(owner: IdentityModel) -> SessionModel:
    return SessionModel.objects.create(
        owner=owner,
        context=SessionContextChoices.CHAT,
        description="a session",
    )


@pytest.fixture
def agent_branch(branch_registry: BranchModelRegistry) -> BranchModel:
    return _by_name(branch_registry["agent"], "agent-2")


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


@pytest.mark.django_db
def test_session_view_renders_thinking(
    session: SessionModel,
    agent_branch: BranchModel,
    admin_client: Client,
):
    """The session transcript is meant to surface the entire exchange, so a
    ThinkingPart the model produced must show up alongside the reply -- not
    only on the message's own change page."""
    response = ModelResponse(
        parts=[
            ThinkingPart(content="reasoning about the answer"),
            TextPart(content="the answer"),
        ]
    )
    _make_message(session, agent_branch, response)

    admin_response = admin_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "reasoning about the answer" in content


@pytest.mark.django_db
def test_session_view_omits_thinking_block_when_absent(
    session: SessionModel,
    agent_branch: BranchModel,
    admin_client: Client,
):
    response = ModelResponse(parts=[TextPart(content="the answer")])
    _make_message(session, agent_branch, response)

    admin_response = admin_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "the answer" in content
    assert "Thinking" not in content


@pytest.mark.django_db
def test_session_view_renders_tool_call(
    session: SessionModel,
    agent_branch: BranchModel,
    admin_client: Client,
):
    """A tool call is its own section, with the tool name in the summary and
    the full (untruncated) args rendered as JSON in the details."""
    response = ModelResponse(
        parts=[ToolCallPart(tool_name="sentinel_op", args={"a": 12, "b": 8})]
    )
    _make_message(session, agent_branch, response)

    admin_response = admin_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "Tool Call: sentinel_op" in content
    assert escape('"a": 12') in content
    assert escape('"b": 8') in content


@pytest.mark.django_db
def test_session_view_omits_tool_call_block_when_absent(
    session: SessionModel,
    agent_branch: BranchModel,
    admin_client: Client,
):
    response = ModelResponse(parts=[TextPart(content="the answer")])
    _make_message(session, agent_branch, response)

    admin_response = admin_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "Tool Call:" not in content


@pytest.mark.django_db
def test_session_view_renders_tool_return(
    session: SessionModel,
    agent_branch: BranchModel,
    admin_client: Client,
):
    """A tool return is its own section too, with the tool name in the
    summary and the full content rendered as JSON in the details."""
    request = ModelRequest(
        parts=[ToolReturnPart(tool_name="sentinel_op", content={"result": 20})]
    )
    _make_message(session, agent_branch, request, role=RoleChoices.TOOL)

    admin_response = admin_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "Tool Return: sentinel_op" in content
    assert escape('"result": 20') in content


@pytest.mark.django_db
def test_session_view_omits_tool_return_block_when_absent(
    session: SessionModel,
    agent_branch: BranchModel,
    admin_client: Client,
):
    response = ModelResponse(parts=[TextPart(content="the answer")])
    _make_message(session, agent_branch, response)

    admin_response = admin_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert "Tool Return:" not in content


@pytest.mark.django_db
def test_session_view_does_not_render_literal_none_for_missing_content(
    session: SessionModel,
    agent_branch: BranchModel,
    admin_client: Client,
):
    """A tool-return-only message has no plain-text content -- the main
    content box must be omitted entirely rather than printing "None"."""
    request = ModelRequest(
        parts=[ToolReturnPart(tool_name="sentinel_op", content={"result": 20})]
    )
    _make_message(session, agent_branch, request, role=RoleChoices.TOOL)

    admin_response = admin_client.get(
        reverse("admin:orm_session_change", args=[session.pk])
    )
    content = admin_response.content.decode()

    assert ">None<" not in content
