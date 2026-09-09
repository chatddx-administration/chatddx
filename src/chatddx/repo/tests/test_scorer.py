import pytest
import pytest_asyncio

from chatddx.core.models import IdentityModel
from chatddx.repo.branch_models import ScorerBranchModel
from chatddx.repo.shufflers.main import ensure_identity_async
from chatddx.repo.shufflers.scorer import (
    DEFAULT_SCORER_NAMES,
    dump_scorer_async,
    dump_scorers_async,
)
from chatddx.repo.trail_models import ScorerTrailModel

pytestmark = pytest.mark.django_db(transaction=True)


@pytest_asyncio.fixture
async def owner():
    return await ensure_identity_async("alex")


@pytest.mark.asyncio
async def test_dump_scorer_creates_a_branch_named_after_it(owner: IdentityModel):
    branch, created = await dump_scorer_async(
        "chatddx.experiment.scorers.exact_match", owner.name
    )

    assert created
    assert branch.name == "chatddx.experiment.scorers.exact_match"
    assert branch.owner_id == owner.pk
    assert branch.target.name == "chatddx.experiment.scorers.exact_match"


@pytest.mark.asyncio
async def test_dump_scorer_is_idempotent(owner: IdentityModel):
    first, first_created = await dump_scorer_async(
        "chatddx.experiment.scorers.exact_match", owner.name
    )
    second, second_created = await dump_scorer_async(
        "chatddx.experiment.scorers.exact_match", owner.name
    )

    assert first_created
    assert not second_created
    assert first.pk == second.pk
    assert (
        await ScorerBranchModel.objects.filter(
            owner=owner, name="chatddx.experiment.scorers.exact_match"
        ).acount()
        == 1
    )


@pytest.mark.asyncio
async def test_dump_scorer_reuses_the_trail_across_owners(owner: IdentityModel):
    """Two owners naming the same scorer share the same (content-addressed)
    ScorerTrailModel row, each behind their own Branch."""
    other = await ensure_identity_async("bob")

    mine, _ = await dump_scorer_async(
        "chatddx.experiment.scorers.exact_match", owner.name
    )
    theirs, _ = await dump_scorer_async(
        "chatddx.experiment.scorers.exact_match", other.name
    )

    assert mine.pk != theirs.pk
    assert mine.target.pk == theirs.target.pk
    assert await ScorerTrailModel.objects.acount() == 1


@pytest.mark.asyncio
async def test_dump_scorers_dumps_every_name(owner: IdentityModel):
    dumped = await dump_scorers_async(DEFAULT_SCORER_NAMES, owner.name)

    names = {branch.name for branch in dumped.values()}
    assert names == set(DEFAULT_SCORER_NAMES)
