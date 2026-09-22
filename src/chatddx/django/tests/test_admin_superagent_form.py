# pyright: basic

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.fields import dict_to_toml, parse_toml_or_dict
from chatddx.core.models import IdentityModel
from chatddx.repo.entities.agent.django import AgentBranchModel
from chatddx.repo.entities.connection.django import ConnectionBranchModel
from chatddx.repo.inventories import InventoryBranchModel

pytestmark = [
    pytest.mark.django_db(transaction=True),
]


def test_super_agent_change_recreates_no_branch(
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    """
    Every trail an agent reaches was given a branch when the agent was
    committed (`commit_closure`), so rendering the change form is a lookup:
    it writes nothing and has nothing to report.
    """
    agent = inventory_fixture_bm["agent"]["some-agent"]

    before = ConnectionBranchModel.objects.count()

    change_url = reverse("admin:orm_superagent_change", args=[agent.pk])
    response = user_client.get(change_url)

    assert response.status_code == 200
    assert not response.context["messages"]
    assert ConnectionBranchModel.objects.count() == before


def test_super_agent_add_and_versioning(
    owner: IdentityModel,
    user_client: Client,
    superagent_post_data,
):
    post_data = superagent_post_data
    assert post_data["instruction"] == "some instructions"
    assert len(post_data["tool_group_tools"]) == 1
    assert isinstance(post_data["tool_group_tools"][0], str)

    existing = AgentBranchModel.objects.filter(
        owner__name=owner.name,
        name="some-agent",
    )

    assert existing.count() == 1

    response = user_client.post(
        reverse("admin:orm_superagent_add"),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    existing = AgentBranchModel.objects.filter(
        owner__name=owner.name,
        name="some-agent",
    )

    assert existing.count() == 1
    some_agent = existing.first()
    assert some_agent is not None

    response = user_client.post(
        reverse("admin:orm_superagent_change", args=[some_agent.pk]),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    existing = AgentBranchModel.objects.filter(
        owner__name=owner.name,
        name="some-agent",
    )

    assert existing.count() == 1
    some_agent = existing.first()
    assert some_agent is not None

    assert some_agent.target.output_type.definition["type"] == "object"

    output_type_def = parse_toml_or_dict(post_data["output_type_definition"])

    assert output_type_def is not None
    assert output_type_def["type"] == "object"
    assert output_type_def["properties"]["age"]["minimum"] == 0

    post_data["output_type_definition"] = dict_to_toml(output_type_def)

    response = user_client.post(
        reverse("admin:orm_superagent_change", args=[some_agent.pk]),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    existing = AgentBranchModel.objects.filter(
        owner__name=owner.name,
        name="some-agent",
    )

    assert existing.count() == 1
    some_agent = existing.first()
    assert some_agent is not None

    output_type_def["properties"]["age"]["minimum"] = 1
    post_data["output_type_definition"] = dict_to_toml(output_type_def)

    response = user_client.post(
        reverse("admin:orm_superagent_change", args=[some_agent.pk]),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    existing = AgentBranchModel.objects.filter(
        owner__name=owner.name,
        name="some-agent",
    )

    assert existing.count() == 2
    some_agent = existing.first()
    assert some_agent is not None

    post_data["output_type_definition"] = "asdf"
    response = user_client.post(
        reverse("admin:orm_superagent_change", args=[some_agent.pk]),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert (
            "Expected '='"
            in response.context["adminform"].form.errors["output_type_definition"][0]
        )


def test_superagent_owners(
    user_client: Client,
    collaborators,
    superagent_post_data,
):
    superagent_post_data["owner"] = collaborators[0].pk
    response = user_client.post(
        reverse("admin:orm_superagent_add"),
        data=superagent_post_data,
        follow=True,
    )

    agent = AgentBranchModel.objects.get(name="some-agent", owner=collaborators[0])
    assert agent.owner.name == "collaborator-1"

    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""


def test_superagent_collaborators(
    user_client: Client,
    collaborators,
    superagent_post_data,
):
    post_data = superagent_post_data

    assert isinstance(post_data["instruction"], str)
    assert post_data["instruction"] == "some instructions"

    post_data_with_collaborators = post_data.copy()
    post_data_with_collaborators["collaborators"] = [c.pk for c in collaborators]

    response = user_client.post(
        reverse("admin:orm_superagent_add"),
        data=post_data_with_collaborators,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    messages = [str(m) for m in response.context["messages"]]
    assert any("updated collaborators" in m for m in messages)

    assert not getattr(response.wsgi_request, "_skip_success_message", False)

    agent_branch = AgentBranchModel.objects.get(name="some-agent")

    assert collaborators == list(agent_branch.collaborators.all())
