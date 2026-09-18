# pyright: basic
import pytest
import pytest_asyncio
from django.contrib.contenttypes.models import ContentType

from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identity_async
from chatddx.repo.families.pydantic import BranchDetailsPatch
from chatddx.repo.inventories import (
    InventoryBranchModel,
    InventoryBranchSpec,
    InventoryFormDataOut,
    InventoryTrailSchema,
    ParsedInventory,
)
from chatddx.repo.parsers.inventory import parse
from chatddx.repo.shufflers import inventory
from chatddx.utils import make_async


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker):
    with django_db_blocker.unblock():
        from django.test.utils import setup_databases

        with django_db_blocker.unblock():
            setup_databases(
                verbosity=0,
                interactive=False,
                keepdb=False,
            )
        yield


@pytest.fixture(autouse=True)
def clear_content_type_cache():
    ContentType.objects.clear_cache()
    yield


@pytest_asyncio.fixture
async def owner() -> IdentityModel:
    return await ensure_identity_async("alex")


@pytest_asyncio.fixture
async def other_owner() -> IdentityModel:
    return await ensure_identity_async("other")


@pytest_asyncio.fixture
async def parsed_inventory(
    request: pytest.FixtureRequest, owner: IdentityModel
) -> ParsedInventory:
    path = request.path.parent / settings.TEST_INVENTORY_PATH
    branch_details = BranchDetailsPatch(owner=owner.name)
    return parse(path, branch_details)


@pytest_asyncio.fixture
async def inventory_fixture_ts(
    parsed_inventory: ParsedInventory,
) -> InventoryTrailSchema:
    return await make_async(inventory.trail_schema)(parsed_inventory)


@pytest_asyncio.fixture
async def inventory_fixture_commit_branchless(
    inventory_fixture_ts: InventoryTrailSchema,
    owner: IdentityModel,
) -> inventory.InventoryCommitReceipt:
    return await make_async(inventory.commit_trail_schemas)(
        inventory_fixture_ts, owner.name
    )


@pytest_asyncio.fixture
async def inventory_fixture_commit(
    parsed_inventory: ParsedInventory,
    owner: IdentityModel,
) -> inventory.InventoryCommitReceipt:
    return await make_async(inventory.commit_parsed_inventory)(parsed_inventory)


@pytest_asyncio.fixture
async def inventory_fixture_bm(
    owner: IdentityModel,
    inventory_fixture_commit,
) -> InventoryBranchModel:
    return await make_async(inventory.owned_inventory)(owner.name)


@pytest_asyncio.fixture
async def inventory_fixture_bs(inventory_fixture_bm: InventoryBranchModel):
    return await make_async(InventoryBranchSpec.model_validate)(inventory_fixture_bm)


@pytest_asyncio.fixture
async def inventory_fixture_fdo(
    inventory_fixture_bs: InventoryBranchSpec,
) -> InventoryFormDataOut:
    return await make_async(inventory.form_data_out)(inventory_fixture_bs)
