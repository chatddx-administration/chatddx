from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.repo.inventories import InventoryBranchModel

if TYPE_CHECKING:
    from chatddx.history.models import ExperimentModel, RunModel

# The prompt the agent is sent and the reply the stubbed agent gives back; the
# reply hits the first row of `scored-case`'s expectation, so a run that goes
# all the way through scores 100.
CASE_PAYLOAD = "a patient presents with a cough"
AGENT_REPLY = "most likely community-acquired pneumonia"

# The worker's fixtures import history where they're used: history still
# speaks the old model, and importing it here would keep the provisioning
# tests beside them from running on the registry's own settings.


@pytest.fixture
def experiment(
    owner: IdentityModel,
    inventory_fixture_bm: InventoryBranchModel,
) -> ExperimentModel:
    from chatddx.history.models import ExperimentModel

    case = inventory_fixture_bm["case"]["scored-case"]
    expect_branch = case.expects.first()
    assert expect_branch is not None

    return ExperimentModel.objects.create(
        owner=owner,
        agent=inventory_fixture_bm["agent"]["agent-2"].target,
        case=case.target,
        expect=expect_branch.target,
    )


@pytest.fixture
def queued_run(owner: IdentityModel, experiment: ExperimentModel) -> RunModel:
    from chatddx.history.models import RunModel

    return RunModel.objects.create(
        owner=owner,
        experiment=experiment,
        status=RunStatusChoices.QUEUED,
    )
