# pyright: basic

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any, override

import pytest
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from pytest_django import DjangoDbBlocker
from rich.console import Console
from typer.testing import CliRunner

from chatddx.core import settings
from chatddx.dev.fake_vllm import FakeTransport
from chatddx.repl.commands import handle
from chatddx.repl.shell import Repl
from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import EntityName
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.parsers.inventory import parse
from chatddx.repo.queries import head_of
from chatddx.repo.store.branch import commit

# the old portal and its worker, kept for reference: nothing runs them
collect_ignore = ["django-old-ref"]

PORTAL = Path(__file__).parent / "django" / "portal"

TEST_INVENTORY = settings.INVENTORY_PATH / "test-inventory.toml"
TEST_GIFTBAG = settings.INVENTORY_PATH / "test-giftbag-inventory.toml"

# The tests' people come on in alphabetical order: alice, whom the seed is
# for and a repl or a client speaks as unless told otherwise, then bob, carol,
# dave and erin. No one real: an identity whose part matters more than who it
# is goes by that part (archive, guest, nobody, other).

type Provision = Callable[..., list[str]]
type Say = Callable[..., str]
type SayAs = Callable[..., Say]
type Recommit = Callable[..., None]


def pytest_ignore_collect(collection_path: Path) -> bool | None:
    """
    The portal's tests run under its settings, the rest's under the minimal
    ones, and each run leaves the other's out (AGENTS.md).
    """
    inside = collection_path == PORTAL or PORTAL in collection_path.parents

    if apps.is_installed("chatddx.django.portal"):
        return None if inside or collection_path in PORTAL.parents else True

    return True if inside else None


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup: None, django_db_blocker: DjangoDbBlocker) -> None:
    # seeded once: each test's transaction starts from it, and rolls back to it
    with django_db_blocker.unblock():
        _ = _init_data()


@pytest.fixture(autouse=True)
def clear_content_type_cache():
    ContentType.objects.clear_cache()
    yield


@pytest.fixture(scope="session")
def test_inventory() -> ParsedInventory:
    return parse(TEST_INVENTORY)


@pytest.fixture(scope="session")
def test_giftbag() -> ParsedInventory:
    return parse(TEST_GIFTBAG)


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
def provision() -> Provision:
    return _init_data


def _init_data(*options: str, user: str = "alice") -> list[str]:
    """init-data for `user` on the test inventory and giftbag: what it printed."""
    from chatddx.manage import app

    result = CliRunner().invoke(
        app,
        [
            "init-data",
            user,
            "--inventory",
            str(TEST_INVENTORY),
            "--giftbag-inventory",
            str(TEST_GIFTBAG),
            *options,
        ],
    )
    assert result.exit_code == 0, result.output
    return result.output.splitlines()


@pytest.fixture
def fake() -> FakeTransport:
    """The fake vLLM: it answers what a run sends it, as vLLM would."""
    return FakeTransport()


class Stalling(FakeTransport):
    """The fake vLLM, stalling after a few tokens as a busy server can."""

    def __init__(self, after: int = 3):
        super().__init__()
        self.after: int = after
        self.stalled: bool = False

    @override
    async def next_token(self, generated: int, /) -> None:
        if generated >= self.after and not self.stalled:
            self.stalled = True
            await asyncio.sleep(10)


@pytest.fixture
def stalling() -> Stalling:
    """The fake vLLM, stalling mid-answer: a run is still on its way when stopped."""
    return Stalling()


@pytest.fixture
def say_as(fake: FakeTransport) -> SayAs:
    """
    A repl of `identity`'s, unseeded, its runs sent through `transport` or the
    fake vLLM: say lines to it, and read what it wrote since.
    """

    def say_as(identity: str = "alice", transport: Any = None) -> Say:
        return say_to(
            Repl(
                identity, Console(record=True, width=200), transport or fake, seed=None
            )
        )

    return say_as


def say_to(repl: Repl) -> Say:
    def say(*lines: str) -> str:
        for line in lines:
            assert handle(repl, line)

        return repl.console.export_text()

    return say


@pytest.fixture
def recommit() -> Recommit:
    return _recommit


def _recommit(entity: EntityName, archived: str, /, **details: Any) -> None:
    """
    The trail of the archive's `archived` of `entity`, committed again as
    `details` have it: a new version of the archive's, or, named or owned
    otherwise, a copy.
    """
    bundle = entity_of(entity)
    head = head_of(
        bundle.branch_model.objects.all(), settings.ARCHIVE_IDENTITY_NAME, archived
    )
    assert head is not None, f"the archive has no {entity} '{archived}'"

    _ = commit(
        head.trail,
        bundle.branch_details.model_validate(
            {**head.details, "name": archived, "owner": head.owner.name, **details}
        ),
    )
