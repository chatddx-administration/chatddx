import pytest

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.history.models import ExperimentModel, RunModel
from chatddx.repo.inventories import InventoryBranchModel

# The prompt the agent is sent and the reply the stubbed agent gives back; the
# reply hits the first row of `scored-case`'s expectation, so a run that goes
# all the way through scores 100.
CASE_PAYLOAD = "a patient presents with a cough"
AGENT_REPLY = "most likely community-acquired pneumonia"


@pytest.fixture
def experiment(
    owner: IdentityModel,
    inventory_fixture_bm: InventoryBranchModel,
) -> ExperimentModel:
    case = inventory_fixture_bm["case"]["scored-case"]
    expect = case.expects.first()
    assert expect is not None

    return ExperimentModel.objects.create(
        owner=owner,
        agent=inventory_fixture_bm["agent"]["agent-2"].target,
        case=case.target,
        expect=expect,
    )


@pytest.fixture
def queued_run(owner: IdentityModel, experiment: ExperimentModel) -> RunModel:
    return RunModel.objects.create(
        owner=owner,
        experiment=experiment,
        status=RunStatusChoices.QUEUED,
    )
