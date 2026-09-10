import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from django.utils import timezone
from pydantic_ai import ModelResponse, TextPart
from pydantic_core import to_jsonable_python

from chatddx.core.choices import RoleChoices, RunStatusChoices
from chatddx.core.models import IdentityModel, TagModel
from chatddx.experiment.models import ExperimentModel, RunModel
from chatddx.history.models import MessageModel, SessionModel
from chatddx.repo.base import BranchModel
from chatddx.repo.branch_models import AgentBranchModel, CaseBranchModel
from chatddx.repo.shufflers.expect import dump_expect_async
from chatddx.repo.shufflers.experiment import create_experiment_async
from chatddx.repo.shufflers.main import dump_trail_registry_async, ensure_identity_async
from chatddx.repo.shufflers.scorer import dump_scorer_async
from chatddx.repo.shufflers.wipe import wipe_data_async
from chatddx.repo.trail_models import AgentTrailModel, CaseTrailModel, ScorerTrailModel
from chatddx.utils import make_async

pytestmark = pytest.mark.django_db(transaction=True)


def _target(branch: BranchModel):
    return branch.target


target_async = make_async(_target)


def by_name(branches: dict[int, BranchModel], name: str) -> BranchModel:
    return next(branch for branch in branches.values() if branch.name == name)


@pytest_asyncio.fixture
async def owner():
    return await ensure_identity_async("alex")


@pytest_asyncio.fixture
async def other_owner():
    return await ensure_identity_async("bob")


@pytest_asyncio.fixture
async def branches(owner: IdentityModel):
    path = Path(__file__).parent / "data/test-registry.toml"
    return await dump_trail_registry_async(path, owner.name)


@pytest_asyncio.fixture
async def case_1(branches: dict[str, dict[int, BranchModel]]) -> CaseTrailModel:
    return await target_async(by_name(branches["case"], "case-1"))


@pytest_asyncio.fixture
async def agent(branches: dict[str, dict[int, BranchModel]]) -> AgentTrailModel:
    return await target_async(by_name(branches["agent"], "agent-2"))


@pytest_asyncio.fixture
async def owned_graph(
    owner: IdentityModel,
    branches: dict[str, dict[int, BranchModel]],
    case_1: CaseTrailModel,
    agent: AgentTrailModel,
) -> RunModel:
    scorer_branch, _ = await dump_scorer_async(
        "chatddx.experiment.scorers.exact_match", owner.name
    )
    scorer = await target_async(scorer_branch)

    _ = await dump_expect_async(
        case=case_1,
        scorer=scorer,
        payload="the expected answer",
        owner_name=owner.name,
    )

    experiment = await create_experiment_async(
        owner_name=owner.name,
        agent=agent,
        case=case_1,
        tags=["baseline"],
        scorer=scorer,
    )

    session = await SessionModel.objects.acreate(owner=owner)
    message = ModelResponse(parts=[TextPart(content="the expected answer")])
    await MessageModel.objects.acreate(
        agent_id=agent.pk,
        session=session,
        kind=message.kind,
        run_id=uuid.uuid4(),
        role=RoleChoices.ASSISTANT,
        payload=to_jsonable_python(message),
        timestamp=timezone.now(),
    )

    run = await RunModel.objects.acreate(
        owner=owner,
        experiment=experiment,
        session=session,
        status=RunStatusChoices.COMPLETED,
    )

    await TagModel.objects.acreate(owner=owner, name="a-tag")

    return run


@pytest.mark.asyncio
async def test_wipe_data_removes_everything_owned(
    owner: IdentityModel,
    owned_graph: RunModel,
):
    assert await wipe_data_async(owner.name)

    assert not await IdentityModel.objects.filter(name=owner.name).aexists()
    assert not await RunModel.objects.filter(owner=owner).aexists()
    assert not await SessionModel.objects.filter(owner=owner).aexists()
    assert not await MessageModel.objects.filter(
        session=owned_graph.session_id
    ).aexists()
    assert not await ExperimentModel.objects.filter(owner=owner).aexists()
    assert not await AgentBranchModel.objects.filter(owner=owner).aexists()
    assert not await CaseBranchModel.objects.filter(owner=owner).aexists()
    assert not await TagModel.objects.filter(owner=owner).aexists()


@pytest.mark.asyncio
async def test_wipe_data_leaves_shared_trail_content_alone(
    owner: IdentityModel,
    owned_graph: RunModel,
    case_1: CaseTrailModel,
):
    scorer_count_before = await ScorerTrailModel.objects.acount()
    assert scorer_count_before > 0

    assert await wipe_data_async(owner.name)

    assert await CaseTrailModel.objects.filter(pk=case_1.pk).aexists()
    assert await ScorerTrailModel.objects.acount() == scorer_count_before


@pytest.mark.asyncio
async def test_wipe_data_never_touches_another_owners_data(
    owner: IdentityModel,
    other_owner: IdentityModel,
    owned_graph: RunModel,
    branches: dict[str, dict[int, BranchModel]],
    case_1: CaseTrailModel,
    agent: AgentTrailModel,
):
    _ = await dump_expect_async(
        case=case_1,
        scorer=None,
        payload="a different answer",
        owner_name=other_owner.name,
    )
    other_experiment = await create_experiment_async(
        owner_name=other_owner.name,
        agent=agent,
        case=case_1,
        tags=None,
    )

    assert await wipe_data_async(owner.name)

    assert await IdentityModel.objects.filter(name=other_owner.name).aexists()
    assert await ExperimentModel.objects.filter(pk=other_experiment.pk).aexists()


@pytest.mark.asyncio
async def test_wipe_data_is_a_noop_for_an_unknown_owner():
    assert not await wipe_data_async("no-such-owner")
