# pyright: basic
import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.models import IdentityModel
from chatddx.repo.entities.agent.django import AgentBranchModel
from chatddx.repo.entities.tool.django import ToolBranchModel
from chatddx.repo.inventories import InventoryFormDataOut

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.django_db
def test_tool_add_missing_required_field_shows_single_error(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    data = inventory_fixture_fdo.tool
    some_key, *_rest = data.keys()

    post_data = data[some_key].model_dump(exclude_none=True)
    post_data["name"] = "a-new-tool"
    post_data["command"] = ""

    response = user_client.post(
        reverse("admin:orm_tool_add"),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200

    form_errors = response.context["adminform"].form.errors["command"]
    assert len(form_errors) == 1


@pytest.mark.django_db
def test_connection_add_missing_required_field_shows_single_error(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    data = inventory_fixture_fdo.connection
    some_key, *_rest = data.keys()

    post_data = data[some_key].model_dump(exclude_none=True)
    post_data["name"] = "a-new-connection"
    post_data["model"] = ""

    response = user_client.post(
        reverse("admin:orm_connection_add"),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200

    form_errors = response.context["adminform"].form.errors["model"]
    assert len(form_errors) == 1


def test_tool_edit_versions_then_delete_removes_it(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    data = inventory_fixture_fdo.tool
    some_key = "some-tool"

    post_data = data[some_key].model_dump()

    assert isinstance(post_data["command"], str)
    assert post_data["command"] == "some-tool"

    existing = ToolBranchModel.objects.filter(
        owner__name=owner.name,
        name=some_key,
    )

    assert existing.count() == 1
    some_tool = existing.first()
    assert some_tool is not None

    post_data["command"] = "some-command-asdf"

    response = user_client.post(
        reverse("admin:orm_tool_change", args=[some_tool.pk]),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    (message,) = [str(m) for m in response.context["messages"]]
    assert "changed successfully" in message

    versions = ToolBranchModel.objects.filter(
        owner__name=owner.name,
        name=some_key,
    ).count()

    assert versions == 2
    some_tool = existing.first()
    assert some_tool is not None

    response = user_client.post(
        reverse("admin:orm_tool_delete", args=[some_tool.pk]),
        data={"post": "yes"},
        follow=True,
    )

    existing = ToolBranchModel.objects.filter(
        owner__name=owner.name,
        name=some_key,
    )

    assert existing.count() == 1
    some_tool = existing.first()
    assert some_tool is not None

    response = user_client.post(
        reverse("admin:orm_tool_delete", args=[some_tool.pk]),
        data={"post": "yes"},
        follow=True,
    )
    assert existing.count() == 0


@pytest.mark.django_db
def test_agent_change_view_renders(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    versions = list(
        AgentBranchModel.objects.filter(
            owner_id=owner.pk,
            name="some-agent",
        ).order_by("timestamp")
    )

    v2_url = reverse("admin:orm_agent_change", args=[versions[0].pk])
    response = user_client.get(v2_url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_output_type_add(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    data = inventory_fixture_fdo.output_type
    some_key, *_rest = data.keys()

    post_data = data[some_key].model_dump(exclude_none=True)

    assert isinstance(post_data["definition"], str)
    post_data["definition"] = "asdf=1"

    response = user_client.post(
        reverse("admin:orm_outputtype_add"),
        data=post_data,
        follow=True,
    )

    (message,) = [str(m) for m in response.context["messages"]]
    assert "added successfully" in message


@pytest.mark.django_db
def test_tool_group_add(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    data = inventory_fixture_fdo.tool_group
    add_url = reverse("admin:orm_toolgroup_add")
    some_key = "tool_group-1"

    post_data = data[some_key].model_dump(exclude_none=True)
    post_data["name"] = some_key

    assert isinstance(post_data["instructions"], str)
    assert post_data["instructions"] == "Tool group instructions 1"
    assert len(post_data["tools"]) == 3

    response = user_client.post(
        add_url,
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    (message,) = [str(m) for m in response.context["messages"]]
    assert "up to date" in message


@pytest.mark.django_db
def test_agent_add(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    data = inventory_fixture_fdo.agent
    some_key = "some-agent"

    post_data = data[some_key].model_dump(by_alias=True)

    assert isinstance(post_data["instruction"], str)
    assert post_data["instruction"] == "some instructions"

    assert "connection_id" not in post_data
    assert post_data["connection"] is not None

    assert (
        AgentBranchModel.objects.get(name=some_key).target.instruction.definition
        == "some instructions"
    )

    response = user_client.post(
        reverse("admin:orm_agent_add"),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    (message,) = [str(m) for m in response.context["messages"]]
    assert "up to date" in message


@pytest.mark.django_db
def test_agent_add_with_collaborators(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
    collaborators: list[IdentityModel],
):
    data = inventory_fixture_fdo.agent
    some_key = "some-agent"

    post_data = data[some_key].model_dump(by_alias=True)

    assert isinstance(post_data["instruction"], str)
    assert post_data["instruction"] == "some instructions"

    assert "connection_id" not in post_data
    assert post_data["connection"] is not None

    agent_branch = AgentBranchModel.objects.get(name=some_key)
    assert agent_branch.target.instruction.definition == "some instructions"

    response = user_client.post(
        reverse("admin:orm_agent_add"),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    (message,) = [str(m) for m in response.context["messages"]]
    assert "up to date" in message

    post_data_with_collaborators = post_data.copy()
    post_data_with_collaborators["collaborators"] = [c.pk for c in collaborators]

    response = user_client.post(
        reverse("admin:orm_agent_add"),
        data=post_data_with_collaborators,
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    messages = [str(m) for m in response.context["messages"]]
    assert any("updated collaborators" in m for m in messages)

    assert not getattr(response.wsgi_request, "_skip_success_message", False)

    agent_branch.refresh_from_db()
    assert collaborators == list(agent_branch.collaborators.all())
