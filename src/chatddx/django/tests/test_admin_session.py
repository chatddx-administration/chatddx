import uuid

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from pydantic_ai import ModelResponse, TextPart, ThinkingPart
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
    response: ModelResponse,
) -> MessageModel:
    return MessageModel.objects.create(
        agent_id=agent_branch.target.pk,
        session=session,
        kind=response.kind,
        run_id=uuid.uuid4(),
        role=RoleChoices.ASSISTANT,
        payload=to_jsonable_python(response),
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
