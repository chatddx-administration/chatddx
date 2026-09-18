from typing import cast

import pytest

from chatddx.core.models import IdentityModel
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import CaseBranchSpec, CaseTrailSchema
from chatddx.repo.entities.expect.pydantic import ExpectTrailSchema
from chatddx.repo.entities.scorer.pydantic import ScorerTrailSchema
from chatddx.repo.families.pydantic import BranchSchemaDetails
from chatddx.repo.inventories import InventoryBranchSpec
from chatddx.repo.shufflers.branch import commit_async, get_branch_async
from chatddx.utils import make_async

pytestmark = pytest.mark.django_db(transaction=True)


PAYLOAD_1 = "case payload 1"
EXPECT_1_A = "expect payload 1 for scorer a"
EXPECT_1_B = "expect payload 1 for scorer b"


async def case_canon(owner_name: str, name: str = "case-1") -> CaseBranchSpec:
    return cast(
        CaseBranchSpec,
        await get_branch_async(
            entity_name="case",
            branch_name=name,
            owner_name=owner_name,
        ),
    )


@make_async
def expect_payloads(branch: CaseBranchModel) -> list[str]:
    return [expect.payload for expect in branch.expects.all()]


@make_async
def oldest_version(owner: IdentityModel, name: str = "case-1") -> CaseBranchModel:
    return CaseBranchModel.objects.filter(
        owner=owner,
        name=name,
    ).earliest("timestamp")


@pytest.mark.asyncio
async def test_case_1(inventory_fixture_bs: InventoryBranchSpec):
    case_1 = inventory_fixture_bs.case["case-1"]
    assert case_1.name == "case-1"
    assert case_1.target.payload == PAYLOAD_1
    assert case_1.tags == ["tag-1", "tag-2"]
    assert case_1.expects[0].payload == EXPECT_1_A
    assert case_1.expects[0].scorer.command == "scorer-a command"


@pytest.mark.asyncio
async def test_expects_belong_to_the_owner_not_to_the_payload(
    inventory_fixture_commit: object,
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    scorer = ScorerTrailSchema(command="scorer-x command")

    _ = await commit_async(
        trail=scorer,
        branch_details=BranchSchemaDetails(name="scorer-x", owner=other_owner.name),
    )
    _ = await commit_async(
        trail=ExpectTrailSchema(payload="another expectation", scorer=scorer),
        branch_details=BranchSchemaDetails(
            name="case-1|scorer-x",
            owner=other_owner.name,
        ),
    )
    _ = await commit_async(
        trail=CaseTrailSchema(payload=PAYLOAD_1),
        branch_details=BranchSchemaDetails(
            name="case-1",
            owner=other_owner.name,
            expects=["case-1|scorer-x"],
        ),
    )

    mine = await case_canon(owner.name)
    theirs = await case_canon(other_owner.name)

    # the payload is the same case, so both own a branch of the same trail
    assert mine.target.id == theirs.target.id

    assert [expect.payload for expect in mine.expects] == [EXPECT_1_A, EXPECT_1_B]
    assert [expect.payload for expect in theirs.expects] == ["another expectation"]


@pytest.mark.asyncio
async def test_a_new_case_version_snapshots_the_expects_it_supersedes(
    inventory_fixture_commit: object,
    owner: IdentityModel,
):
    created = await commit_async(
        trail=CaseTrailSchema(payload="case payload 1, rewritten"),
        branch_details=BranchSchemaDetails(name="case-1", owner=owner.name),
    )
    assert created

    canon = await case_canon(owner.name)
    assert canon.target.payload == "case payload 1, rewritten"
    assert [expect.payload for expect in canon.expects] == [EXPECT_1_A, EXPECT_1_B]

    # the version it superseded keeps its own set
    superseded = await oldest_version(owner)
    assert await expect_payloads(superseded) == [EXPECT_1_A, EXPECT_1_B]


@pytest.mark.asyncio
async def test_named_expects_reach_the_canon_of_an_unchanged_case(
    inventory_fixture_commit: object,
    owner: IdentityModel,
):
    created = await commit_async(
        trail=CaseTrailSchema(payload=PAYLOAD_1),
        branch_details=BranchSchemaDetails(
            name="case-1",
            owner=owner.name,
            expects=["expect-1-a"],
        ),
    )

    # the case itself is untouched, its expectations are not
    assert not created

    canon = await case_canon(owner.name)
    assert [expect.payload for expect in canon.expects] == [EXPECT_1_A]
