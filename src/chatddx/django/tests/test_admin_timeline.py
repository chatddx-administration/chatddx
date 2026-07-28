# src/chatddx/django/repo/tests/test_admin_timeline.py
# pyright: basic
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import pytest
from django.contrib.auth.models import User
from django.db.models import Q
from django.test import Client
from django.urls import get_resolver, reverse

from chatddx.core.fields import dict_to_toml, parse_toml_or_dict
from chatddx.core.models import IdentityModel
from chatddx.repo import proxies
from chatddx.repo.branch_models import (
    AgentBranchModel,
    BranchModelRegistry,
    ConnectionBranchModel,
    ToolBranchModel,
)
from chatddx.repo.form_data_in import SamplingParamsFormDataIn
from chatddx.repo.form_data_out import TemplateData
from chatddx.repo.shufflers.main import (
    dump_trail_registry,
    load_form_data,
    qs_super_agent,
)
from chatddx.repo.trail_models import AgentTrailModel, ConnectionTrailModel

parameters: list[
    tuple[
        str,
        str,
        Any,
        Callable[[int], str | int],
    ]
] = [
    (
        "agent",
        "instructions",
        proxies.Agent,
        lambda i: f"instruction {i}",
    ),
    (
        "tool_group",
        "instructions",
        proxies.ToolGroup,
        lambda i: f"instruction {i}",
    ),
    (
        "output_type",
        "definition",
        proxies.OutputType,
        lambda i: f"value={i}",
    ),
    (
        "connection",
        "model",
        proxies.Connection,
        lambda i: f"model {i}",
    ),
    (
        "sampling_params",
        "seed",
        proxies.SamplingParams,
        lambda i: i,
    ),
    (
        "tool",
        "command",
        proxies.Tool,
        lambda i: f"cmd_{i}",
    ),
]


@pytest.mark.django_db
def debug_admin_route(admin_client: Client):
    resolver = get_resolver()

    print("\n--- ALL AVAILABLE URL NAMES ---")
    for url_pattern in resolver.url_patterns:
        if hasattr(url_pattern, "url_patterns"):
            for sub_pattern in url_pattern.url_patterns:
                if hasattr(sub_pattern, "name") and sub_pattern.name:
                    print(f"Name: {sub_pattern.name} -> Pattern: {sub_pattern.pattern}")
        else:
            if hasattr(url_pattern, "name") and url_pattern.name:
                print(f"Name: {url_pattern.name} -> Pattern: {url_pattern.pattern}")
    assert True


@pytest.fixture(autouse=True)
def branch_registry(owner: IdentityModel):
    path = Path(__file__).parent / "data/test-registry.toml"
    return dump_trail_registry(path, owner_name=owner.name)


@pytest.fixture
def owner(admin_user: User):
    owner, _created = IdentityModel.objects.get_or_create(name=admin_user.username)
    return owner


@pytest.fixture
def collaborators():
    owner1, _created = IdentityModel.objects.get_or_create(name="alex")
    owner2, _created = IdentityModel.objects.get_or_create(name="olof")
    return [owner1, owner2]


@pytest.fixture
def template_data(branch_registry: BranchModelRegistry):
    form_data: dict[str, Any] = defaultdict(dict)

    for bundle, branches in branch_registry.items():
        for branch_model in branches.values():
            form_data[bundle][branch_model.name] = load_form_data(branch_model)

    return TemplateData.model_validate(form_data)


@pytest.fixture
def superagent_post_data(template_data):
    post_data_relations: dict[str, dict[str, Any]] = {
        "connection_": template_data.connection["some-connection"].model_dump(
            exclude_none=True
        ),
        "sampling_params_": template_data.sampling_params[
            "some-sampling_params"
        ].model_dump(exclude_none=True),
        "tool_group_": template_data.tool_group["some-tool_group"].model_dump(
            exclude_none=True
        ),
        "output_type_": template_data.output_type["some-output_type"].model_dump(
            exclude_none=True
        ),
    }
    return template_data.agent["some-agent"].model_dump(exclude_none=True) | {
        f"{outer}{inner}": value
        for outer, inner_dict in post_data_relations.items()
        for inner, value in inner_dict.items()
    }


@pytest.mark.django_db
def test_super_agent_2(
    branch_registry: BranchModelRegistry,
    admin_client: Client,
):
    agent = next(iter(branch_registry["agent"].values()))
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

    agent = branch_registry["agent"][1]
    fingerprint = agent.target.connection.fingerprint

    change_url = reverse("admin:orm_superagent_change", args=[agent.id])
    response = admin_client.get(change_url)
    assert response.status_code == 200

    assert not response.context["messages"]


@pytest.mark.django_db
def test_super_agent(
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
def test_append(
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
def test_view(
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
def test_ownership(
    template_data: TemplateData,
    owner: IdentityModel,
):
    connection_fields = [field.name for field in ConnectionTrailModel._meta.fields]

    agent_trails = AgentTrailModel.objects.filter(
        branches__owner__name=owner.name
    ).distinct()
    assert len(agent_trails) == 5

    all_owned_connections = (
        ConnectionTrailModel.objects.filter(
            Q(agenttrailmodel__branches__owner__name=owner.name)
            | Q(branches__owner__name=owner.name)
        )
        .values(*connection_fields, "branches__name")
        .distinct()
    )
    assert all_owned_connections[0]["branches__name"] == "some-connection"
    assert len(all_owned_connections) == 3

    agent_connections = ConnectionTrailModel.objects.filter(
        agenttrailmodel__branches__owner__name=owner.name
    ).distinct()
    assert len(agent_connections) == 3

    new_owner = IdentityModel.objects.create(name="alex")
    some_agent = AgentBranchModel.objects.filter(name="some-agent").first()
    some_agent.owner_id = new_owner.pk
    some_agent.save()

    (some_agent_trail,) = AgentTrailModel.objects.filter(
        branches__owner__name="alex"
    ).distinct()
    assert some_agent_trail is not None
    assert some_agent_trail.pk == some_agent.target.pk

    agent_trails = AgentTrailModel.objects.filter(
        branches__owner__name=owner.name
    ).distinct()
    assert len(agent_trails) == 4

    agent_connections = ConnectionTrailModel.objects.filter(
        agenttrailmodel__branches__owner__name=owner.name
    ).distinct()
    assert len(agent_connections) == 2

    all_owned_connections = ConnectionTrailModel.objects.filter(
        Q(agenttrailmodel__branches__owner__name=owner.name)
        | Q(branches__owner__name=owner.name)
    ).distinct()
    assert len(all_owned_connections) == 3


@pytest.mark.django_db
def test_sampling_params(template_data: TemplateData):
    data = template_data.sampling_params

    assert list(data.keys()) == [
        "some-sampling_params",
        "sampling_params-1",
        "sampling_params-2",
        "deterministic",
        "no-thinking",
    ]
    assert data["some-sampling_params"].stop_sequences == ""
    assert data["sampling_params-1"].stop_sequences == "\\n\\n\nEND"
    assert data["sampling_params-2"].stop_sequences == "END"

    form_data_out_1 = SamplingParamsFormDataIn.model_validate(
        data["some-sampling_params"].model_dump(exclude_none=True)
    )
    assert form_data_out_1.stop_sequences == []

    form_data_out_2 = SamplingParamsFormDataIn.model_validate(
        data["sampling_params-1"].model_dump(exclude_none=True)
    )
    assert form_data_out_2.stop_sequences == ["\\n\\n", "END"]


@pytest.mark.django_db
def test_output_type(
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
def test_tool_group(template_data: TemplateData, admin_client: Client):
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
def test_agent_qs(owner: IdentityModel):
    qs = proxies.Agent.objects.filter(name="some-agent", owner_id=owner.pk)
    agent = qs_super_agent(qs, owner.name).first()
    assert agent is not None
    assert agent.connection_id is not None


@pytest.mark.django_db
def test_agent(template_data: TemplateData, admin_client: Client):
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
def test_agent_collaborators(
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


@pytest.mark.django_db
@pytest.mark.parametrize("test_model, test_field, model_class, mutator", parameters)
def test_idempotent_save_prevents_duplicates(
    admin_client: Client,
    template_data: TemplateData,
    owner: IdentityModel,
    test_model: str,
    test_field: str,
    model_class: proxies.BranchProxy,
    mutator: Callable[[int], str],
):
    data = getattr(template_data, test_model)
    admin_name = test_model.replace("_", "")

    add_url = reverse(f"admin:orm_{admin_name}_add")

    some_key, *_rest = data.keys()

    response = admin_client.post(
        add_url,
        data=data[some_key].model_dump(by_alias=True, exclude_none=True),
        follow=True,
    )

    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    (message,) = [str(m) for m in response.context["messages"]]
    assert "up to date" in message

    response = admin_client.post(
        add_url,
        data=data[some_key].model_dump(by_alias=True, exclude_none=True),
        follow=True,
    )

    (message,) = [str(m) for m in response.context["messages"]]
    assert "up to date" in message

    timeline = model_class.objects.filter(owner_id=owner.pk, name=some_key)
    assert len(timeline) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("test_model, test_field, model_class, mutator", parameters)
def test_name_change_creates_new_branch(
    admin_client: Client,
    template_data: TemplateData,
    owner: IdentityModel,
    test_model: str,
    test_field: str,
    model_class: proxies.BranchProxy,
    mutator: Callable[[int], str],
):
    data = getattr(template_data, test_model)
    admin_name = test_model.replace("_", "")

    add_url = reverse(f"admin:orm_{admin_name}_add")

    some_key, another_key, *_rest = data.keys()

    data[some_key].name = another_key

    admin_client.post(
        add_url,
        data=data[some_key].model_dump(by_alias=True, exclude_none=True),
        follow=True,
    )
    timeline = model_class.objects.filter(owner_id=owner.pk, name=some_key)
    assert len(timeline) == 1

    timeline = model_class.objects.filter(owner_id=owner.pk, name=another_key)
    assert len(timeline) == 2


@pytest.mark.django_db
@pytest.mark.parametrize("test_model, test_field, model_class, mutator", parameters)
def test_pager_context_navigation(
    admin_client: Client,
    template_data: TemplateData,
    owner: IdentityModel,
    test_model: str,
    test_field: str,
    model_class: proxies.BranchProxy,
    mutator: Callable[[int], str],
):
    data = getattr(template_data, test_model)
    admin_name = test_model.replace("_", "")

    add_url = reverse(f"admin:orm_{admin_name}_add")

    some_key, _another_key, *_rest = data.keys()

    for i in range(3):
        setattr(data[some_key], test_field, mutator(i))
        admin_client.post(
            add_url,
            data=data[some_key].model_dump(by_alias=True, exclude_none=True),
            follow=True,
        )

    versions = list(
        model_class.objects.filter(
            owner_id=owner.pk,
            name=some_key,
        ).order_by("timestamp")
    )

    v2_url = reverse(f"admin:orm_{admin_name}_change", args=[versions[1].pk])
    response = admin_client.get(v2_url)
    assert response.status_code == 200
    assert "prev_" in response.context
    assert "next_" in response.context
    assert response.context["version_info"]["current"] == 2
    assert response.context["version_info"]["total"] == 4

    v1_url = reverse(f"admin:orm_{admin_name}_change", args=[versions[0].pk])
    response = admin_client.get(v1_url)
    assert response.status_code == 200
    assert "next_" in response.context
    assert response.context["version_info"]["current"] == 1
    assert response.context["version_info"]["total"] == 4

    v4_url = reverse(f"admin:orm_{admin_name}_change", args=[versions[3].pk])
    response = admin_client.get(v4_url)
    assert response.status_code == 200
    assert "prev_" in response.context
    assert response.context["version_info"]["current"] == 4
    assert response.context["version_info"]["total"] == 4
