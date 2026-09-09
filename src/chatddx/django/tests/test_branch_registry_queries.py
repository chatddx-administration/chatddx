import pytest
from django.db.models import Q

from chatddx.core.models import IdentityModel
from chatddx.repo import proxies
from chatddx.repo.branch_models import AgentBranchModel
from chatddx.repo.form_data_in import SamplingParamsFormDataIn
from chatddx.repo.form_data_out import TemplateData
from chatddx.repo.shufflers.main import qs_super_agent
from chatddx.repo.trail_models import AgentTrailModel, ConnectionTrailModel


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
def test_agent_qs(owner: IdentityModel):
    qs = proxies.Agent.objects.filter(name="some-agent", owner_id=owner.pk)
    agent = qs_super_agent(qs, owner.name).first()
    assert agent is not None
    assert agent.connection_id is not None
