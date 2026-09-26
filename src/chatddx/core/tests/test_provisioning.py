"""
`chatddx init-data` and `chatddx wipe-data`, run as the command line runs
them: on the test inventory and giftbag, and once on the live ones. The
session's seed is the test inventory init-data gave alice; a test of seeding
itself starts from an empty database.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from chatddx.conftest import Provision, Say, SayAs
from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.history.models import ConversationModel, RunModel, TrialModel
from chatddx.manage import app
from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import ENTITY_NAMES
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.names import short_fingerprint
from chatddx.repo.parsers.inventory import parse
from chatddx.repo.store.inventory import owned_inventory

pytestmark = pytest.mark.django_db

ARCHIVE = settings.ARCHIVE_IDENTITY_NAME

NOTHING: dict[str, set[str]] = {entity: set() for entity in ENTITY_NAMES}

NO_HISTORY = [
    "[score]: removed 0",
    "[run]: removed 0, unshared 0",
    "[message]: removed 0",
    "[conversation]: removed 0, unshared 0",
    "[trial]: removed 0",
]


def run(*args: str) -> list[str]:
    """The lines a command prints, once it has run to completion."""
    result = CliRunner().invoke(app, args, catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return result.output.splitlines()


def receipts(parsed: ParsedInventory, label: str, receipt: str) -> list[str]:
    """What init-data prints for every record of `parsed`."""
    return [
        f"[{label} {entity}]: {name} ({receipt} {short_fingerprint(trail.fingerprint)})"
        for entity in ENTITY_NAMES
        for name, (trail, _) in getattr(parsed, entity).items()
    ]


def names(parsed: ParsedInventory) -> dict[str, set[str]]:
    """The names of the records of `parsed`, by entity."""
    return {entity: set(getattr(parsed, entity)) for entity in ENTITY_NAMES}


def owned(owner_name: str) -> dict[str, set[str]]:
    """The names of the branches `owner_name` owns, by entity."""
    inventory = owned_inventory(owner_name)
    return {entity: set(inventory[entity]) for entity in ENTITY_NAMES}


def shared_with(identity_name: str) -> dict[str, set[str]]:
    """The names of the branches `identity_name` collaborates on, by entity."""
    return {
        entity: set(
            entity_of(entity)
            .branch_model.objects.filter(collaborators__name=identity_name)
            .values_list("name", flat=True)
        )
        for entity in ENTITY_NAMES
    }


def versions() -> dict[str, int]:
    """How many versions there are of every entity's branches."""
    return {
        entity: entity_of(entity).branch_model.objects.count()
        for entity in ENTITY_NAMES
    }


@pytest.mark.slow
@pytest.mark.usefixtures("unseeded")
def test_init_data_provisions_the_live_inventory_and_giftbag_by_default():
    inventory = parse(settings.INVENTORY_PATH / "inventory.toml")
    giftbag = parse(settings.INVENTORY_PATH / "giftbag-inventory.toml")

    assert run("init-data", "alice", "--with-giftbag") == (
        receipts(inventory, "archive", "created")
        + receipts(giftbag, "giftbag", "created")
    )
    assert owned(ARCHIVE) == names(inventory)
    assert shared_with("alice") == names(inventory)
    assert owned("alice") == names(giftbag)


@pytest.mark.usefixtures("unseeded")
def test_init_data_archives_the_inventory_and_shares_it_with_each_user(
    provision: Provision, test_inventory: ParsedInventory
):
    inventory = test_inventory

    assert provision() == receipts(inventory, "archive", "created")

    archived = owned_inventory(ARCHIVE)

    for entity in ENTITY_NAMES:
        for name, (trail, _) in getattr(inventory, entity).items():
            branch_model = archived[entity][name]

            assert branch_model.trail.fingerprint == trail.fingerprint
            assert [c.name for c in branch_model.collaborators.all()] == ["alice"]

    assert owned(ARCHIVE) == names(inventory)
    assert owned("alice") == NOTHING

    before = versions()

    assert provision() == receipts(inventory, "archive", "validated")
    assert versions() == before

    _ = provision(user="bob")

    assert shared_with("alice") == names(inventory)
    assert shared_with("bob") == names(inventory)


def test_init_data_with_giftbag_gives_the_user_their_own(
    provision: Provision, test_inventory: ParsedInventory, test_giftbag: ParsedInventory
):
    giftbag = test_giftbag

    assert provision("--with-giftbag") == (
        receipts(test_inventory, "archive", "validated")
        + receipts(giftbag, "giftbag", "created")
    )

    assert owned("alice") == names(giftbag)
    assert owned("alice")["stack"] == set()

    mine = owned_inventory("alice")
    archived = owned_inventory(ARCHIVE)

    for entity in ENTITY_NAMES:
        for name, branch_model in mine[entity].items():
            assert branch_model.trail_id == archived[entity][name].trail_id

    plan = mine["configuration"]["plan"]
    tags = [(tag.owner.name, tag.entity, tag.name) for tag in plan.tags.all()]
    assert tags == [("alice", "configuration", "ddx")]


def test_init_data_keeps_the_archive_shared_as_it_changes(tmp_path: Path):
    path = tmp_path / "inventory.toml"

    def write(description: str) -> ParsedInventory:
        _ = path.write_text(
            f'[tool.lookup]\nname = "lookup"\ndescription = "{description}"\n'
        )
        return parse(path)

    _ = write("Look it up.")
    _ = run("init-data", "alice", "--inventory", str(path))
    _ = run("init-data", "bob", "--inventory", str(path))

    changed = write("Look it up, and say where.")

    assert run("init-data", "alice", "--inventory", str(path)) == receipts(
        changed, "archive", "created"
    )

    lookup = owned_inventory(ARCHIVE)["tool"]["lookup"]
    assert lookup.version_count == 2
    assert [c.name for c in lookup.collaborators.all()] == ["alice", "bob"]


def test_init_data_reads_both_inventories_before_writing(tmp_path: Path):
    giftbag = tmp_path / "giftbag.toml"
    _ = giftbag.write_text('[tool.lookup]\nname = "lookup"\ncolour = "blue"\n')
    before = versions()

    result = CliRunner().invoke(
        app,
        ["init-data", "bob", "--with-giftbag", "--giftbag-inventory", str(giftbag)],
    )

    assert result.exit_code == 1
    assert result.stderr.startswith(f"{giftbag}: tool 'lookup': unknown key 'colour'")

    assert versions() == before
    assert not IdentityModel.objects.filter(name="bob").exists()


def test_wipe_data_takes_back_what_init_data_gave_and_init_data_gives_it_again(
    provision: Provision, test_inventory: ParsedInventory, test_giftbag: ParsedInventory
):
    inventory, giftbag = test_inventory, test_giftbag
    _ = provision("--with-giftbag")
    _ = provision("--with-giftbag", user="bob")

    assert run("wipe-data", "alice") == NO_HISTORY + [
        f"[{entity}]: removed {len(getattr(giftbag, entity))}, "
        + f"unshared {len(getattr(inventory, entity))}"
        for entity in ENTITY_NAMES
    ]

    assert owned("alice") == NOTHING
    assert shared_with("alice") == NOTHING

    assert owned(ARCHIVE) == names(inventory)
    assert owned("bob") == names(giftbag)
    assert shared_with("bob") == names(inventory)

    assert provision("--with-giftbag") == (
        receipts(inventory, "archive", "validated")
        + receipts(giftbag, "giftbag", "created")
    )
    assert shared_with("alice") == names(inventory)
    assert owned("alice") == names(giftbag)


def test_wipe_data_of_nobody_removes_nothing():
    assert run("wipe-data", "nobody") == NO_HISTORY + [
        f"[{entity}]: removed 0, unshared 0" for entity in ENTITY_NAMES
    ]
    assert not IdentityModel.objects.filter(name="nobody").exists()


def ran_test_tools(say: Say) -> None:
    """A run of test-tools, on the user's own tools, written down."""
    written = say("cell test-tools qwen3-8b-awq@fake", "run case-1")

    assert "recorded as run 1" in written


def test_wipe_data_takes_back_the_user_s_history_too(
    provision: Provision, say_as: SayAs
):
    _ = provision("--with-giftbag")
    ran_test_tools(say_as("alice"))

    assert run("wipe-data", "alice")[:5] == [
        "[score]: removed 1",
        "[run]: removed 1, unshared 0",
        "[message]: removed 6",
        "[conversation]: removed 1, unshared 0",
        "[trial]: removed 1",
    ]
    assert not RunModel.objects.exists()
    assert not TrialModel.objects.exists()
    assert owned("alice") == NOTHING


def test_wipe_data_keeps_a_user_whose_branches_another_s_run_read(
    provision: Provision, say_as: SayAs, test_giftbag: ParsedInventory
):
    _ = provision("--with-giftbag")
    _ = provision(user="bob")
    ran_test_tools(say_as("alice"))

    bob = IdentityModel.objects.get(name="bob")
    for model in (RunModel, ConversationModel):
        _ = model.objects.update(owner=bob)

    result = CliRunner().invoke(app, ["wipe-data", "alice"])

    assert result.exit_code == 1
    assert "alice is kept: others' runs or scores read its branches" in result.output
    assert owned("alice") == names(test_giftbag)
    assert RunModel.objects.count() == 1
