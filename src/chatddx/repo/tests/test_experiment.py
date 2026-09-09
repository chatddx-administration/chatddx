from pathlib import Path

import pytest
import pytest_asyncio

from chatddx.core.models import IdentityModel
from chatddx.experiment.models import ExperimentModel
from chatddx.repo.base import BranchModel
from chatddx.repo.shufflers.expect import dump_expect_async
from chatddx.repo.shufflers.experiment import (
    create_experiment_async,
    dump_experiments_async,
    find_expect_async,
)
from chatddx.repo.shufflers.main import (
    dump_trail_registry_async,
    ensure_identity_async,
)
from chatddx.repo.trail_models import CaseTrailModel
from chatddx.utils import make_async

pytestmark = pytest.mark.django_db(transaction=True)


def _target(branch: BranchModel):
    return branch.target


target_async = make_async(_target)


@pytest_asyncio.fixture
async def owner():
    return await ensure_identity_async("alex")


@pytest_asyncio.fixture
async def branches(owner: IdentityModel):
    path = Path(__file__).parent / "data/test-registry.toml"
    return await dump_trail_registry_async(path, owner.name)


def by_name(branches: dict[int, BranchModel], name: str) -> BranchModel:
    return next(branch for branch in branches.values() if branch.name == name)


@pytest_asyncio.fixture
async def case_1(branches: dict[str, dict[int, BranchModel]]) -> CaseTrailModel:
    return await target_async(by_name(branches["case"], "case-1"))


@pytest_asyncio.fixture
async def expect_for_case_1(
    owner: IdentityModel,
    branches: dict[str, dict[int, BranchModel]],
    case_1: CaseTrailModel,
):
    output_type = await target_async(by_name(branches["output_type"], "output_type-1"))
    branch, _ = await dump_expect_async(
        case=case_1,
        output_type=output_type,
        payload="the expected answer",
        owner_name=owner.name,
    )
    return await target_async(branch)


@pytest.mark.asyncio
async def test_create_experiment_pins_agent_case_and_expect(
    owner: IdentityModel,
    branches: dict[str, dict[int, BranchModel]],
    case_1: CaseTrailModel,
    expect_for_case_1,
):
    agent = await target_async(by_name(branches["agent"], "agent-2"))

    experiment = await create_experiment_async(
        owner_name=owner.name,
        agent=agent,
        case=case_1,
        tags=["baseline", "smoke"],
    )

    assert experiment.owner_id == owner.pk
    assert experiment.agent_id == agent.pk
    assert experiment.case_id == case_1.pk
    assert experiment.expect_id == expect_for_case_1.pk
    assert experiment.tags == "baseline, smoke"
    assert experiment.tag_list == ["baseline", "smoke"]
    assert experiment.uuid is not None


@pytest.mark.asyncio
async def test_create_experiment_warns_without_a_fixed_seed(
    owner: IdentityModel,
    branches: dict[str, dict[int, BranchModel]],
    case_1: CaseTrailModel,
    expect_for_case_1,
):
    # agent-1 uses sampling_params-1, which has no seed set.
    agent = await target_async(by_name(branches["agent"], "agent-1"))

    with pytest.warns(UserWarning, match="no fixed sampling seed"):
        await create_experiment_async(
            owner_name=owner.name,
            agent=agent,
            case=case_1,
            tags=None,
        )


@pytest.mark.asyncio
async def test_create_experiment_with_fixed_seed_does_not_warn(
    owner: IdentityModel,
    branches: dict[str, dict[int, BranchModel]],
    case_1: CaseTrailModel,
    expect_for_case_1,
    recwarn: pytest.WarningsRecorder,
):
    # agent-2 merges in sampling_params-2, which fixes seed=0.
    agent = await target_async(by_name(branches["agent"], "agent-2"))

    await create_experiment_async(
        owner_name=owner.name,
        agent=agent,
        case=case_1,
        tags=None,
    )

    assert len(recwarn) == 0


@pytest.mark.asyncio
async def test_create_experiment_without_a_matching_expect_raises(
    owner: IdentityModel,
    branches: dict[str, dict[int, BranchModel]],
    case_1: CaseTrailModel,
):
    # "swift" uses its own output_type; nothing has dumped an Expect for it.
    agent = await target_async(by_name(branches["agent"], "swift"))

    assert await find_expect_async(agent, case_1, owner.name) is None

    with pytest.raises(ValueError, match="no Expect"):
        await create_experiment_async(
            owner_name=owner.name,
            agent=agent,
            case=case_1,
            tags=None,
        )


@pytest.mark.asyncio
async def test_dump_experiments_is_idempotent_and_skips_bad_entries(
    owner: IdentityModel,
    branches: dict[str, dict[int, BranchModel]],
    case_1: CaseTrailModel,
    expect_for_case_1,
):
    experiments_dir = Path(__file__).parent / "data/experiments"

    dumped = await dump_experiments_async(experiments_dir, owner.name)

    assert len(dumped) == 1
    assert await ExperimentModel.objects.filter(owner=owner).acount() == 1

    (experiment,) = dumped.values()
    assert experiment.tag_list == ["smoke"]

    dumped_again = await dump_experiments_async(experiments_dir, owner.name)

    assert dumped_again.keys() == dumped.keys()
    assert await ExperimentModel.objects.filter(owner=owner).acount() == 1
