import pytest

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.history.models import ExperimentModel, RunModel
from chatddx.repo.inventories import InventoryBranchModel

# The prompt the agent is sent and the output the stubbed agent returns; the
# output's first item satisfies `scored-case`'s expectation, so a run that
# goes all the way through scores 100.
CASE_PAYLOAD = "a patient presents with a cough"
AGENT_OUTPUT = ["community-acquired pneumonia", "copd"]


@pytest.fixture
def experiment(
    owner: IdentityModel,
    inventory_fixture_bm: InventoryBranchModel,
) -> ExperimentModel:
    case = inventory_fixture_bm["case"]["scored-case"]
    expect_branch = case.expects.first()
    assert expect_branch is not None

    return ExperimentModel.objects.create(
        owner=owner,
        agent=inventory_fixture_bm["agent"]["diagnostician"].target,
        case=case.target,
        expect=expect_branch.target,
    )


@pytest.fixture
def queued_run(owner: IdentityModel, experiment: ExperimentModel) -> RunModel:
    return RunModel.objects.create(
        owner=owner,
        experiment=experiment,
        status=RunStatusChoices.QUEUED,
    )
