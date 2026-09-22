from typing import cast

import pytest

from chatddx.core.choices import ToolChoices
from chatddx.core.models import IdentityModel
from chatddx.repo.entities.case.pydantic import CaseBranchSpec
from chatddx.repo.entities.tool.pydantic import ToolFormDataIn, ToolTrailSchema
from chatddx.repo.families.pydantic import BranchSchemaDetails
from chatddx.repo.inventories import InventoryBranchModel
from chatddx.repo.shufflers.branch import (
    commit_async,
    get_branch_async,
    get_branch_model_async,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.django_db(transaction=True),
]


async def test_model_from_schema(
    inventory_fixture_bm: InventoryBranchModel,
    owner: IdentityModel,
):
    _ = inventory_fixture_bm
    branch_model = await get_branch_async(
        entity_name="agent",
        branch_name="agent-1",
        owner_name=owner.name,
    )
    assert branch_model is not None
    assert branch_model.id is not None
    assert branch_model.name == "agent-1"


async def test_cases_from_dir(
    inventory_fixture_bm: IdentityModel,
    owner: IdentityModel,
):
    _ = inventory_fixture_bm

    branch_spec = await get_branch_async(
        entity_name="case",
        branch_name="case-1",
        owner_name=owner.name,
    )
    case_branch_spec = cast(CaseBranchSpec, branch_spec)

    assert case_branch_spec.name == "case-1"
    assert case_branch_spec.target.payload == "case payload 1"


async def test_tool(owner: IdentityModel):

    data = {
        "name": "tool",
        "command": "cmd",
        "type": ToolChoices.FUNCTION,
    }

    form_data = ToolFormDataIn.model_validate(data)
    schema = ToolTrailSchema.model_validate(form_data.model_dump())
    name = form_data.name or ""

    created = await commit_async(
        branch_details=BranchSchemaDetails(
            name=name,
            owner=owner.name,
        ),
        trail=schema,
    )

    tool = await get_branch_model_async(
        "tool",
        owner.name,
        name,
    )
    assert schema.fingerprint == tool.target.fingerprint

    assert created
    assert tool.name == data["name"]

    created = await commit_async(
        branch_details=BranchSchemaDetails(
            name=name,
            owner=owner.name,
        ),
        trail=schema,
    )
    assert not created

    tool = await get_branch_model_async(
        "tool",
        owner.name,
        name,
    )
    assert schema.fingerprint == tool.target.fingerprint
    assert tool.name == data["name"]
