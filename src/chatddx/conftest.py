# pyright: basic
"""
Fixtures the tests of every package share, around one test inventory:
`data/test-inventory.toml`, the live inventory without its case corpus, and
two cases of its own, whose targets every test scores against
(`data/test-targets.toml`).

- A test that needs no database reads it parsed: `test_inventory`.
- repo, below every command, commits it through its own inventory functions:
  `parsed_inventory`, and the `inventory_fixture_*` built on it.
- Everywhere else, a test that needs it in the database seeds it as a user
  would, through init-data: `provision`.
- A test of the live data itself reads the live inventory.
"""

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
    InventoryBranchSpec,
    InventoryFormDataOut,
    InventoryTrailSchema,
    ParsedInventory,
)
from chatddx.repo.parsers.inventory import parse
from chatddx.repo.shufflers import inventory
from chatddx.utils import make_async

TEST_INVENTORY = settings.INVENTORY_PATH / "test-inventory.toml"
TEST_TARGETS = settings.INVENTORY_PATH / "test-targets.toml"


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


@pytest.fixture(autouse=True)
def test_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TARGETS_PATH", TEST_TARGETS)


@pytest.fixture(scope="session")
def test_inventory() -> ParsedInventory:
    return parse(TEST_INVENTORY)


@pytest.fixture
def provision() -> Callable[..., None]:
    """init-data, run as the command line runs it, on the test inventory."""
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
