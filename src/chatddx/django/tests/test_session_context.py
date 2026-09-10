import pytest

from chatddx.core.choices import SessionContextChoices
from chatddx.core.models import IdentityModel
from chatddx.history.models import SessionModel
from chatddx.history.session import start_session
from chatddx.repo.base import BranchModel
from chatddx.repo.branch_models import BranchModelRegistry


def _by_name(branches: dict[int, BranchModel], name: str) -> BranchModel:
    return next(branch for branch in branches.values() if branch.name == name)


def test_start_session_requires_context():
    """context has no default -- omitting it is a caller bug, not something
    to paper over with an implicit fallback context."""
    with pytest.raises(TypeError):
        start_session(owner_id=1, agent_id=1)  # pyright: ignore[reportCallIssue]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_start_session_stores_the_given_context(
    owner: IdentityModel,
    branch_registry: BranchModelRegistry,
):
    agent_branch = _by_name(branch_registry["agent"], "agent-2")

    session = await start_session(
        owner_id=owner.pk,
        agent_id=agent_branch.pk,
        context=SessionContextChoices.EXPERIMENT,
    )

    assert session.context == SessionContextChoices.EXPERIMENT

    stored = await SessionModel.objects.aget(pk=session.id)
    assert stored.context == SessionContextChoices.EXPERIMENT
