import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from django.utils import timezone
from pydantic_ai import ModelResponse, TextPart
from pydantic_core import to_jsonable_python

from chatddx.core.choices import RoleChoices, RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.experiment.models import ExperimentModel, RunModel
from chatddx.experiment.scorers import exact_match, regex_match
from chatddx.history.models import MessageModel, SessionModel
from chatddx.repo.base import BranchModel
from chatddx.repo.shufflers.expect import dump_expect_async
from chatddx.repo.shufflers.experiment import create_experiment_async
from chatddx.repo.shufflers.main import dump_trail_registry_async, ensure_identity_async
from chatddx.repo.shufflers.scorer import dump_scorer_async
from chatddx.repo.trail_models import AgentTrailModel, CaseTrailModel
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
async def agent(branches: dict[str, dict[int, BranchModel]]) -> AgentTrailModel:
    return await target_async(by_name(branches["agent"], "agent-2"))


@pytest_asyncio.fixture
async def experiment(
    owner: IdentityModel,
    branches: dict[str, dict[int, BranchModel]],
    case_1: CaseTrailModel,
    agent: AgentTrailModel,
) -> ExperimentModel:
    _ = await dump_expect_async(
        case=case_1,
        scorer=None,
        payload="the expected answer",
        owner_name=owner.name,
    )

    return await create_experiment_async(
        owner_name=owner.name,
        agent=agent,
        case=case_1,
        tags=None,
    )


async def run_with_reply(
    *,
    owner: IdentityModel,
    experiment: ExperimentModel,
    branches: dict[str, dict[int, BranchModel]],
    agent: AgentTrailModel,
    content: str,
) -> RunModel:
    """A COMPLETED Run whose session has a single assistant reply, the way
    a real Run's session looks once `run_from_session` has recorded its
    result (see chatddx.runtime.runners.on_result)."""
    agent_branch = by_name(branches["agent"], "agent-2")

    session = await SessionModel.objects.acreate(
        owner=owner,
        default_agent_id=agent_branch.pk,
    )

    message = ModelResponse(parts=[TextPart(content=content)])
    await MessageModel.objects.acreate(
        agent_id=agent.pk,
        session=session,
        kind=message.kind,
        run_id=uuid.uuid4(),
        role=RoleChoices.ASSISTANT,
        payload=to_jsonable_python(message),
        timestamp=timezone.now(),
    )

    return await RunModel.objects.acreate(
        owner=owner,
        experiment=experiment,
        session=session,
        status=RunStatusChoices.COMPLETED,
    )


@pytest.mark.asyncio
async def test_exact_match_scores_a_correct_reply_as_correct(
    owner: IdentityModel,
    experiment: ExperimentModel,
    branches: dict[str, dict[int, BranchModel]],
    agent: AgentTrailModel,
):
    run = await run_with_reply(
        owner=owner,
        experiment=experiment,
        branches=branches,
        agent=agent,
        content="the expected answer",
    )

    result = await make_async(exact_match)(run)

    assert result == {
        "correct": True,
        "expected": "the expected answer",
    }


@pytest.mark.asyncio
async def test_exact_match_scores_a_wrong_reply_as_incorrect(
    owner: IdentityModel,
    experiment: ExperimentModel,
    branches: dict[str, dict[int, BranchModel]],
    agent: AgentTrailModel,
):
    run = await run_with_reply(
        owner=owner,
        experiment=experiment,
        branches=branches,
        agent=agent,
        content="a completely different answer",
    )

    result = await make_async(exact_match)(run)

    assert result == {
        "correct": False,
        "expected": "the expected answer",
    }


@pytest.mark.asyncio
async def test_exact_match_treats_a_missing_reply_as_incorrect(
    owner: IdentityModel,
    experiment: ExperimentModel,
):
    session = await SessionModel.objects.acreate(owner=owner)
    run = await RunModel.objects.acreate(
        owner=owner,
        experiment=experiment,
        session=session,
        status=RunStatusChoices.COMPLETED,
    )

    result = await make_async(exact_match)(run)

    assert result == {
        "correct": False,
        "expected": "the expected answer",
    }


REGEX_MATCH_PAYLOAD = (
    "pneumonia\ncopd | ((exacerbation | obstructive) & pulmonary)\na b | c"
)


@pytest_asyncio.fixture
async def regex_experiment(
    owner: IdentityModel,
    branches: dict[str, dict[int, BranchModel]],
    case_1: CaseTrailModel,
    agent: AgentTrailModel,
) -> ExperimentModel:
    scorer_branch, _ = await dump_scorer_async(
        "chatddx.experiment.scorers.regex_match", owner.name
    )
    scorer = await target_async(scorer_branch)

    _ = await dump_expect_async(
        case=case_1,
        scorer=scorer,
        payload=REGEX_MATCH_PAYLOAD,
        owner_name=owner.name,
    )

    return await create_experiment_async(
        owner_name=owner.name,
        agent=agent,
        case=case_1,
        tags=None,
        scorer=scorer,
    )


@pytest.mark.asyncio
async def test_regex_match_scores_a_first_line_match_as_100(
    owner: IdentityModel,
    regex_experiment: ExperimentModel,
    branches: dict[str, dict[int, BranchModel]],
    agent: AgentTrailModel,
):
    run = await run_with_reply(
        owner=owner,
        experiment=regex_experiment,
        branches=branches,
        agent=agent,
        content="likely community-acquired pneumonia",
    )

    result = await make_async(regex_match)(run)

    assert result["score"] == 100
    assert result["matched_row"] == "pneumonia"


@pytest.mark.asyncio
async def test_regex_match_scores_a_second_line_match_as_100_over_2(
    owner: IdentityModel,
    regex_experiment: ExperimentModel,
    branches: dict[str, dict[int, BranchModel]],
    agent: AgentTrailModel,
):
    run = await run_with_reply(
        owner=owner,
        experiment=regex_experiment,
        branches=branches,
        agent=agent,
        content="obstructive pulmonary disease flare-up",
    )

    result = await make_async(regex_match)(run)

    assert result["score"] == 50
    assert result["matched_row"] == "copd | ((exacerbation | obstructive) & pulmonary)"


@pytest.mark.asyncio
async def test_regex_match_scores_a_third_line_match_as_100_over_3(
    owner: IdentityModel,
    regex_experiment: ExperimentModel,
    branches: dict[str, dict[int, BranchModel]],
    agent: AgentTrailModel,
):
    run = await run_with_reply(
        owner=owner,
        experiment=regex_experiment,
        branches=branches,
        agent=agent,
        content="the note only says a b here",
    )

    result = await make_async(regex_match)(run)

    assert result["score"] == pytest.approx(100 / 3)
    assert result["matched_row"] == "a b | c"


@pytest.mark.asyncio
async def test_regex_match_scores_no_match_as_0(
    owner: IdentityModel,
    regex_experiment: ExperimentModel,
    branches: dict[str, dict[int, BranchModel]],
    agent: AgentTrailModel,
):
    run = await run_with_reply(
        owner=owner,
        experiment=regex_experiment,
        branches=branches,
        agent=agent,
        content="no findings of note",
    )

    result = await make_async(regex_match)(run)

    assert result["score"] == 0
    assert result["matched_row"] is None


@pytest.mark.asyncio
async def test_regex_match_treats_a_missing_reply_as_0(
    owner: IdentityModel,
    regex_experiment: ExperimentModel,
):
    session = await SessionModel.objects.acreate(owner=owner)
    run = await RunModel.objects.acreate(
        owner=owner,
        experiment=regex_experiment,
        session=session,
        status=RunStatusChoices.COMPLETED,
    )

    result = await make_async(regex_match)(run)

    assert result["score"] == 0
    assert result["matched_row"] is None
