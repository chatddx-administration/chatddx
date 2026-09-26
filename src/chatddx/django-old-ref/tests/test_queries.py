# pyright: basic
import pytest
from django.db.models import Q

from chatddx.core.models import IdentityModel
from chatddx.django.portal.qs import qs_super_agent
from chatddx.repo.entities.agent.django import Agent, AgentBranchModel, AgentTrailModel
from chatddx.repo.entities.connection.django import ConnectionTrailModel
from chatddx.repo.entities.sampling_params.pydantic import SamplingParamsFormDataIn
from chatddx.repo.inventories import InventoryFormDataOut
from chatddx.repo.store.inventory import InventoryCommitReceipt

pytestmark = [
    pytest.mark.django_db(transaction=True),
]


def test_ownership(
    inventory_fixture_commit: InventoryCommitReceipt,
    owner: IdentityModel,
):
    _ = inventory_fixture_commit
    connection_fields = [field.name for field in ConnectionTrailModel._meta.fields]

    agent_trails = AgentTrailModel.objects.filter(
        branches__owner__name=owner.name
    ).distinct()
    assert len(agent_trails) == 4

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
    assert len(agent_connections) == 2

    new_owner = IdentityModel.objects.create(name="foo")
    some_agent = AgentBranchModel.objects.filter(name="some-agent").first()
    assert some_agent is not None
    some_agent.owner_id = new_owner.pk
    some_agent.save()

    (some_agent_trail,) = AgentTrailModel.objects.filter(
        branches__owner__name="foo"
    ).distinct()
    assert some_agent_trail is not None
    assert some_agent_trail.pk == some_agent.target.pk

    agent_trails = AgentTrailModel.objects.filter(
        branches__owner__name=owner.name
    ).distinct()
    assert len(agent_trails) == 3

    agent_connections = ConnectionTrailModel.objects.filter(
        agenttrailmodel__branches__owner__name=owner.name
    ).distinct()
    assert len(agent_connections) == 1

    all_owned_connections = ConnectionTrailModel.objects.filter(
        Q(agenttrailmodel__branches__owner__name=owner.name)
        | Q(branches__owner__name=owner.name)
    ).distinct()
    assert len(all_owned_connections) == 3


def test_sampling_params(inventory_fixture_fdo: InventoryFormDataOut):
    data = inventory_fixture_fdo.sampling_params

    named = {
        "sampling_params-2",
        "sampling_params-1",
        "some-sampling_params",
    }

    generated = data.keys() - named

    assert len(generated) == 1
    assert generated.pop().startswith("sampling_params ")

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


def test_agent_qs(
    inventory_fixture_commit: InventoryCommitReceipt,
    owner: IdentityModel,
):
    qs = Agent.objects.filter(name="some-agent", owner_id=owner.pk)
    agent = qs_super_agent(qs, owner.name).first()

    assert agent

    connection = agent.connection_branch

    assert connection.trail == agent.target.connection
    assert connection.id
    assert connection.name == "some-connection"


def test_agent_qs_without_the_annotation_says_so(
    inventory_fixture_commit: InventoryCommitReceipt,
    owner: IdentityModel,
):
    agent = Agent.objects.filter(name="some-agent", owner_id=owner.pk).first()

    assert agent

    with pytest.raises(AttributeError, match="annotate_branch_refs"):
        _ = agent.connection_branch
