# src/chatddx/backend/repo/test/test_branches.py
from pathlib import Path

import pytest
import pytest_asyncio

from chatddx.core.models import IdentityModel
from chatddx.repo.base import BranchModel
from chatddx.repo.shufflers.main import (
    dump_cases_async,
    dump_trail_registry_async,
    ensure_identity_async,
    load_branch_async,
)


@pytest_asyncio.fixture(autouse=True)
async def branches(owner: IdentityModel):
    path = Path(__file__).parent / "data/test-registry.toml"
    return await dump_trail_registry_async(path, owner.name)


@pytest_asyncio.fixture
async def owner():
    return await ensure_identity_async("alex")


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_schemas_from_registry(branches: dict[str, dict[int, BranchModel]]):
    assert len(branches["agent"]) == 5
    assert len(branches["connection"]) == 3


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_model_from_schema(owner: IdentityModel):
    branch_model = await load_branch_async(
        bundle_name="agent",
        branch_name="agent-1",
        owner_name=owner.name,
    )
    assert branch_model.id is not None
    assert branch_model.name == "agent-1"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_cases_from_dir(owner: IdentityModel):
    cases_dir = Path(__file__).parent / "data/cases"

    cases = await dump_cases_async(cases_dir, owner.name)
    assert len(cases) == 2

    branch_model = await load_branch_async(
        bundle_name="case",
        branch_name="case-alpha",
        owner_name=owner.name,
    )
    assert branch_model is not None
    assert branch_model.name == "case-alpha"
    assert (
        branch_model.target.payload
        == "A 40-year-old patient presents with fever and cough."
    )
