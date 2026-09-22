import json
import uuid

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from pydantic_ai import ModelResponse, TextPart
from pydantic_core import to_jsonable_python

from chatddx.core.choices import RoleChoices
from chatddx.history.models import MessageModel, SessionModel
from chatddx.history.proxies import Message
from chatddx.repo.entities.agent.django import AgentBranchModel
from chatddx.repo.inventories import InventoryBranchModel

pytestmark = [
    pytest.mark.django_db(transaction=True),
]


@pytest.fixture
def message(
    session: SessionModel,
    inventory_fixture_bm: InventoryBranchModel,
) -> MessageModel:
    response = ModelResponse(parts=[TextPart(content="hello")])
    return MessageModel.objects.create(
        agent_id=inventory_fixture_bm["agent"]["agent-1"].target.pk,
        session=session,
        kind=response.kind,
        run_id=uuid.uuid4(),
        role=RoleChoices.ASSISTANT,
        payload=to_jsonable_python(response),
        timestamp=timezone.now(),
    )


def test_session_field_is_a_link(
    message: MessageModel,
    session: SessionModel,
    user_client: Client,
):
    response = user_client.get(reverse("admin:orm_message_change", args=[message.pk]))
    content = response.content.decode()

    field_html = content.split(">Session</label>")[1][:500]
    assert reverse("admin:orm_session_change", args=[session.pk]) in field_html


def test_agent_field_is_a_link(
    message: MessageModel,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    agent_branch = inventory_fixture_bm["agent"]["agent-1"]
    response = user_client.get(reverse("admin:orm_message_change", args=[message.pk]))
    content = response.content.decode()

    field_html = content.split(">Agent </label>")[1][:500]
    assert reverse("admin:orm_superagent_change", args=[agent_branch.pk]) in field_html


def test_a_reply_carrying_a_list_reads_as_the_list(
    lister: AgentBranchModel,
    session: SessionModel,
    user_client: Client,
):
    # a list is asked for inside an envelope, and that is what a reply holds
    response = ModelResponse(
        parts=[TextPart(content=json.dumps({"response": ["pneumonia", "copd"]}))]
    )
    message = MessageModel.objects.create(
        agent_id=lister.target.pk,
        session=session,
        kind=response.kind,
        run_id=uuid.uuid4(),
        role=RoleChoices.ASSISTANT,
        payload=to_jsonable_python(response),
        timestamp=timezone.now(),
    )

    assert Message.objects.get(pk=message.pk).typed_content == ["pneumonia", "copd"]

    page = user_client.get(reverse("admin:orm_message_change", args=[message.pk]))

    assert page.status_code == 200
