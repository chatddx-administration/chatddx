import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.fields import dict_to_toml, parse_toml_or_dict
from chatddx.core.models import IdentityModel
from chatddx.repo.branch_models import (
    AgentBranchModel,
    BranchModelRegistry,
    ConnectionBranchModel,
)


@pytest.mark.django_db
def test_super_agent_change_recreates_dangling_connection_branch(
    branch_registry: BranchModelRegistry,
    admin_client: Client,
):
    agent = next(a for a in branch_registry["agent"].values() if a.name == "some-agent")
    fingerprint = agent.target.connection.fingerprint

    change_url = reverse("admin:orm_superagent_change", args=[agent.id])
    response = admin_client.get(change_url)
    assert response.status_code == 200

    assert not response.context["messages"]

    _ = ConnectionBranchModel.objects.filter(target=agent.target.connection).delete()

    change_url = reverse("admin:orm_superagent_change", args=[agent.id])
    response = admin_client.get(change_url)
    assert response.status_code == 200

    messages = list(response.context["messages"])

    assert any(fingerprint[:6] in str(m.message) for m in messages), (
        f"'{fingerprint}' not found in: {[m.message for m in messages]}"
    )

    change_url = reverse("admin:orm_superagent_change", args=[agent.id])
    response = admin_client.get(change_url)
    assert response.status_code == 200

    assert not response.context["messages"]


@pytest.mark.django_db
def test_super_agent_add_and_versioning(
    owner: IdentityModel,
    admin_client: Client,
    superagent_post_data,
):
    post_data = superagent_post_data
    assert post_data["instructions"] == "some instructions"
    assert len(post_data["tool_group_tools"]) == 2
    assert isinstance(post_data["tool_group_tools"][0], str)

    existing = AgentBranchModel.objects.filter(
        owner__name=owner.name,
        name="some-agent",
    )

    assert existing.count() == 1

    response = admin_client.post(
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

    response = admin_client.post(
        reverse("admin:orm_superagent_change", args=[existing.first().pk]),
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

    assert existing.first().target.output_type.definition["type"] == "object"

    output_type_def = parse_toml_or_dict(post_data["output_type_definition"])

    assert output_type_def is not None
    assert output_type_def["type"] == "object"
    assert output_type_def["properties"]["age"]["minimum"] == 0

    post_data["output_type_definition"] = dict_to_toml(output_type_def)

    response = admin_client.post(
        reverse("admin:orm_superagent_change", args=[existing.first().pk]),
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

    output_type_def["properties"]["age"]["minimum"] = 1
    post_data["output_type_definition"] = dict_to_toml(output_type_def)

    response = admin_client.post(
        reverse("admin:orm_superagent_change", args=[existing.first().pk]),
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

    post_data["output_type_definition"] = "asdf"
    response = admin_client.post(
        reverse("admin:orm_superagent_change", args=[existing.first().pk]),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert (
            "Expected '='"
            in response.context["adminform"].form.errors["output_type_definition"][0]
        )


@pytest.mark.django_db
def test_superagent_owners(
    admin_client: Client,
    collaborators,
    superagent_post_data,
):
    superagent_post_data["owner"] = collaborators[0].pk
    response = admin_client.post(
        reverse("admin:orm_superagent_add"),
        data=superagent_post_data,
        follow=True,
    )

    agent = AgentBranchModel.objects.get(name="some-agent", owner=collaborators[0])
    assert agent.owner.name == "alex"

    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""


@pytest.mark.django_db
def test_superagent_collaborators(
    admin_client: Client,
    collaborators,
    superagent_post_data,
):
    post_data = superagent_post_data

    assert isinstance(post_data["instructions"], str)
    assert post_data["instructions"] == "some instructions"

    post_data_with_collaborators = post_data.copy()
    post_data_with_collaborators["collaborators"] = [c.pk for c in collaborators]

    response = admin_client.post(
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
