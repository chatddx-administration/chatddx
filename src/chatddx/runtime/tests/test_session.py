import pytest

from chatddx.core.choices import SessionContextChoices
from chatddx.core.models import IdentityModel
from chatddx.history.session import resume_session, start_session
from chatddx.repo.inventories import InventoryBranchSpec
from chatddx.runtime.runners import run_from_session


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_session(inventory_fixture_bs: InventoryBranchSpec, owner: IdentityModel):
    agent = inventory_fixture_bs.agent["qwen3-8b baseline"]

    session = await start_session(owner.pk, agent.id, SessionContextChoices.CHAT)
    result = await run_from_session(session, "say 'aaa'")

    assert result.output in ["aaa", '"aaa"']

    agent_session = await resume_session(owner.pk, session.uuid)

    result = await run_from_session(agent_session, "say it again")
    assert "aaa" in str(result.output)
