"""Add/change/delete flows for the plain, single-model admin forms (tool,
agent, output_type, tool_group).

See test_admin_superagent_form.py for the composite SuperAgent form, and
test_admin_timeline.py for version-history behavior shared across all
branch-backed models.
"""

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.models import IdentityModel
from chatddx.repo.branch_models import AgentBranchModel, ToolBranchModel
from chatddx.repo.form_data_out import TemplateData


@pytest.mark.django_db
def test_tool_edit_versions_then_delete_removes_it(
    template_data: TemplateData,
    owner: IdentityModel,
    admin_client: Client,
):
    data = template_data.tool
    some_key = "some-tool"

    post_data = data[some_key].model_dump()

    assert isinstance(post_data["command"], str)
    assert post_data["command"] == "some-tool"

    existing = ToolBranchModel.objects.filter(
        owner__name=owner.name,
        name=some_key,
    )

    assert existing.count() == 1

    post_data["command"] = "some-command"

    response = admin_client.post(
        reverse("admin:orm_tool_change", args=[existing.first().pk]),
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

    response = admin_client.post(
        reverse("admin:orm_tool_delete", args=[existing.first().pk]),
        data={"post": "yes"},
        follow=True,
    )

    existing = ToolBranchModel.objects.filter(
        owner__name=owner.name,
        name=some_key,
    )

    assert existing.count() == 1

    response = admin_client.post(
        reverse("admin:orm_tool_delete", args=[existing.first().pk]),
        data={"post": "yes"},
        follow=True,
    )
    assert existing.count() == 0


@pytest.mark.django_db
def test_agent_change_view_renders(
    template_data: TemplateData,
    owner: IdentityModel,
    admin_client: Client,
):
    versions = list(
        AgentBranchModel.objects.filter(
            owner_id=owner.pk,
            name="some-agent",
        ).order_by("timestamp")
    )

    v2_url = reverse("admin:orm_agent_change", args=[versions[0].pk])
    response = admin_client.get(v2_url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_output_type_add(
    template_data: TemplateData,
    admin_client: Client,
):
    data = template_data.output_type
    some_key, *_rest = data.keys()

    post_data = data[some_key].model_dump(exclude_none=True)

    assert isinstance(post_data["definition"], str)
    post_data["definition"] = "asdf=1"

    response = admin_client.post(
        reverse("admin:orm_outputtype_add"),
        data=post_data,
        follow=True,
    )

    (message,) = [str(m) for m in response.context["messages"]]
    assert "added successfully" in message


@pytest.mark.django_db
def test_tool_group_add(template_data: TemplateData, admin_client: Client):
    data = template_data.tool_group
    add_url = reverse("admin:orm_toolgroup_add")
    some_key = "tool_group-1"

    post_data = data[some_key].model_dump(exclude_none=True)
    post_data["name"] = some_key

    assert isinstance(post_data["instructions"], str)
    assert post_data["instructions"] == "use these tools"
    assert len(post_data["tools"]) == 3

    response = admin_client.post(
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
def test_agent_add(template_data: TemplateData, admin_client: Client):
    data = template_data.agent
    some_key = "some-agent"

    post_data = data[some_key].model_dump(by_alias=True)

    assert isinstance(post_data["instructions"], str)
    assert post_data["instructions"] == "some instructions"

    assert "connection_id" not in post_data
    assert post_data["connection"] is not None

    assert (
        AgentBranchModel.objects.get(name=some_key).target.instructions
        == "some instructions"
    )

    response = admin_client.post(
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
    template_data: TemplateData,
    admin_client: Client,
    collaborators,
):
    data = template_data.agent
    some_key = "some-agent"

    post_data = data[some_key].model_dump(by_alias=True)

    assert isinstance(post_data["instructions"], str)
    assert post_data["instructions"] == "some instructions"

    assert "connection_id" not in post_data
    assert post_data["connection"] is not None

    agent_branch = AgentBranchModel.objects.get(name=some_key)
    assert agent_branch.target.instructions == "some instructions"

    response = admin_client.post(
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

    response = admin_client.post(
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
