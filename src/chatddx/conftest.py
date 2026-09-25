# pyright: basic

from collections.abc import Callable

import pytest
import pytest_asyncio
from django.contrib.contenttypes.models import ContentType
from typer.testing import CliRunner

from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identity_async
from chatddx.repo.families.pydantic import BranchDetailsPatch
from chatddx.repo.inventories import (
    InventoryBranchModel,
    InventoryBranchOut,
    InventoryFormDataOut,
    InventoryTrailIn,
    ParsedInventory,
)
from chatddx.repo.parsers.inventory import parse
from chatddx.repo.store import inventory
from chatddx.utils import make_async

# the portal's and the API's tests still speak the old datamodel
collect_ignore = ["django/tests"]

TEST_INVENTORY = settings.INVENTORY_PATH / "test-inventory.toml"


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


@pytest.fixture(scope="session")
def test_inventory() -> ParsedInventory:
    return parse(TEST_INVENTORY)


@pytest.fixture
def provision() -> Callable[..., None]:
    from chatddx.manage import app

    def provision(*options: str, user: str = "alex") -> None:
        result = CliRunner().invoke(
            app, ["init-data", user, "--inventory", str(TEST_INVENTORY), *options]
        )
        assert result.exit_code == 0, result.output

    return provision


@pytest_asyncio.fixture
async def owner() -> IdentityModel:
    return await ensure_identity_async("alex")


@pytest_asyncio.fixture
async def other_owner() -> IdentityModel:
    return await ensure_identity_async("other")


@pytest_asyncio.fixture
async def parsed_inventory(owner: IdentityModel) -> ParsedInventory:
    return parse(TEST_INVENTORY, BranchDetailsPatch(owner=owner.name))


@pytest_asyncio.fixture
async def inventory_fixture_ti(
    parsed_inventory: ParsedInventory,
) -> InventoryTrailIn:
    return await make_async(inventory.trails_in)(parsed_inventory)


@pytest_asyncio.fixture
async def inventory_fixture_commit_branchless(
    inventory_fixture_ti: InventoryTrailIn,
    owner: IdentityModel,
) -> inventory.InventoryCommitReceipt:
    return await make_async(inventory.commit_trails_in)(
        inventory_fixture_ti, owner.name
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
async def inventory_fixture_bo(inventory_fixture_bm: InventoryBranchModel):
    return await make_async(InventoryBranchOut.model_validate)(inventory_fixture_bm)


@pytest_asyncio.fixture
async def inventory_fixture_fdo(
    inventory_fixture_bo: InventoryBranchOut,
) -> InventoryFormDataOut:
    return await make_async(inventory.form_data_out)(inventory_fixture_bo)
