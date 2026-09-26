# pyright: basic

from collections.abc import Callable

import pytest
from django.contrib.contenttypes.models import ContentType
from typer.testing import CliRunner

from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identity
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

# the portal's tests still speak the old datamodel
collect_ignore = ["django/tests"]

TEST_INVENTORY = settings.INVENTORY_PATH / "test-inventory.toml"


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker):
    with django_db_blocker.unblock():
        from django.test.utils import setup_databases

        setup_databases(verbosity=0, interactive=False, keepdb=False)
        # seeded once: each test's transaction starts from it, and rolls back to it
        _init_data()
        yield


@pytest.fixture(autouse=True)
def clear_content_type_cache():
    ContentType.objects.clear_cache()
    yield


@pytest.fixture(scope="session")
def test_inventory() -> ParsedInventory:
    return parse(TEST_INVENTORY)


@pytest.fixture
def unseeded() -> None:
    """An empty database, for a test of seeding itself: rolled back with the test."""
    from django.db import connection

    tables = connection.introspection.django_table_names(only_existing=True)

    with connection.cursor() as cursor:
        cursor.execute(
            f"TRUNCATE {', '.join(map(connection.ops.quote_name, tables))} CASCADE"
        )


@pytest.fixture
def provision() -> Callable[..., None]:
    return _init_data


def _init_data(*options: str, user: str = "alex") -> None:
    from chatddx.manage import app

    result = CliRunner().invoke(
        app, ["init-data", user, "--inventory", str(TEST_INVENTORY), *options]
    )
    assert result.exit_code == 0, result.output


@pytest.fixture
def owner() -> IdentityModel:
    return ensure_identity("alex")


@pytest.fixture
def other_owner() -> IdentityModel:
    return ensure_identity("other")


@pytest.fixture
def parsed_inventory(owner: IdentityModel) -> ParsedInventory:
    return parse(TEST_INVENTORY, BranchDetailsPatch(owner=owner.name))


@pytest.fixture
def inventory_fixture_ti(parsed_inventory: ParsedInventory) -> InventoryTrailIn:
    return inventory.trails_in(parsed_inventory)


@pytest.fixture
def inventory_fixture_commit_branchless(
    inventory_fixture_ti: InventoryTrailIn,
    owner: IdentityModel,
) -> inventory.InventoryCommitReceipt:
    return inventory.commit_trails_in(inventory_fixture_ti, owner.name)


@pytest.fixture
def inventory_fixture_commit(
    parsed_inventory: ParsedInventory,
    owner: IdentityModel,
) -> inventory.InventoryCommitReceipt:
    return inventory.commit_parsed_inventory(parsed_inventory)


@pytest.fixture
def inventory_fixture_bm(
    owner: IdentityModel,
    inventory_fixture_commit,
) -> InventoryBranchModel:
    return inventory.owned_inventory(owner.name)


@pytest.fixture
def inventory_fixture_bo(inventory_fixture_bm: InventoryBranchModel):
    return InventoryBranchOut.model_validate(inventory_fixture_bm)


@pytest.fixture
def inventory_fixture_fdo(
    inventory_fixture_bo: InventoryBranchOut,
) -> InventoryFormDataOut:
    return inventory.form_data_out(inventory_fixture_bo)
