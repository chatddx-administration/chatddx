import uuid

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from pydantic_ai import ModelResponse, TextPart
from pydantic_core import to_jsonable_python

from chatddx.core.choices import RoleChoices
from chatddx.core.models import IdentityModel
from chatddx.history.models import MessageModel, SessionModel
from chatddx.repo.base import BranchModel
from chatddx.repo.branch_models import BranchModelRegistry


def _by_name(branches: dict[int, BranchModel], name: str) -> BranchModel:
    return next(branch for branch in branches.values() if branch.name == name)


@pytest.fixture
def session(owner: IdentityModel) -> SessionModel:
    return SessionModel.objects.create(owner=owner, description="a session")


@pytest.fixture
def agent_branch(branch_registry: BranchModelRegistry) -> BranchModel:
    return _by_name(branch_registry["agent"], "agent-2")


@pytest.fixture
def message(
    owner: IdentityModel,
    session: SessionModel,
    agent_branch: BranchModel,
) -> MessageModel:
    response = ModelResponse(parts=[TextPart(content="hello")])
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
def test_session_field_is_a_link(
    message: MessageModel,
    session: SessionModel,
    admin_client: Client,
):
    response = admin_client.get(reverse("admin:orm_message_change", args=[message.pk]))
    content = response.content.decode()

    field_html = content.split(">Session</label>")[1][:500]
    assert reverse("admin:orm_session_change", args=[session.pk]) in field_html


@pytest.mark.django_db
def test_agent_field_is_a_link(
    message: MessageModel,
    agent_branch: BranchModel,
    admin_client: Client,
):
    response = admin_client.get(reverse("admin:orm_message_change", args=[message.pk]))
    content = response.content.decode()

    field_html = content.split(">Agent </label>")[1][:500]
    assert reverse("admin:orm_superagent_change", args=[agent_branch.pk]) in field_html
