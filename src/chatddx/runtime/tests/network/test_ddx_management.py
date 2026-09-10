import json
from pathlib import Path

import pytest
import pytest_asyncio

from chatddx.core.choices import SessionContextChoices
from chatddx.core.models import IdentityModel
from chatddx.history.session import start_session
from chatddx.repo.shufflers.main import dump_trail_registry_async, load_branch_async
from chatddx.runtime.runners import run_from_session, run_from_spec

pytestmark = pytest.mark.network


@pytest_asyncio.fixture(autouse=True)
async def dump_registry(owner: IdentityModel):
    path = Path(__file__).parent / "data/ddx-management.toml"
    return await dump_trail_registry_async(path, owner_name=owner.name)


@pytest_asyncio.fixture
async def owner():
    owner, _created = await IdentityModel.objects.aget_or_create(name="alex")
    return owner


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_ddx_management(owner: IdentityModel):
    data_path = Path(__file__).parent / "data/cases/case_a.txt"
    expects_path = Path(__file__).parent / "data/expects/case_a.json"

    with data_path.open("r") as f:
        case_a = f.read()

    with expects_path.open("r") as f:
        data = json.load(f)

    spec = await load_branch_async(
        bundle_name="agent",
        branch_name="ddx-management",
        owner_name=owner.name,
    )
    assert spec is not None
    result = await run_from_spec(spec.target, case_a)

    print(json.dumps(result.output, indent=2))
    assert result.output == data


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_swift(owner: IdentityModel):
    data_path = Path(__file__).parent / "data/cases/case_b.txt"
    expects_path = Path(__file__).parent / "data/expects/case_b.json"

    with data_path.open("r") as f:
        case_a = f.read()

    with expects_path.open("r") as f:
        data = json.load(f)

    spec = await load_branch_async(
        bundle_name="agent",
        branch_name="swift",
        owner_name=owner.name,
    )

    assert spec is not None

    session = await start_session(owner.pk, spec.id, SessionContextChoices.CHAT)

    run_result = await run_from_session(
        session=session,
        prompt=case_a,
        agent_spec=spec.target,
    )

    assert run_result.output == data


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_retry_prompt(owner: IdentityModel):
    data_path = Path(__file__).parent / "data/cases/case_c.txt"
    expects_path = Path(__file__).parent / "data/expects/case_b.json"

    with data_path.open("r") as f:
        case_a = f.read()

    with expects_path.open("r") as f:
        data = json.load(f)

    spec = await load_branch_async(
        bundle_name="agent",
        branch_name="retry-prompt",
        owner_name=owner.name,
    )

    assert spec is not None

    session = await start_session(owner.pk, spec.id, SessionContextChoices.CHAT)

    run_result = await run_from_session(
        session=session,
        prompt=case_a,
        agent_spec=spec.target,
    )

    assert run_result.output == data
