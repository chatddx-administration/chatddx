"""
`chatddx init-data` and `chatddx wipe-data`, run as the command line runs
them. They need only the registry and the identities its branches hang off,
so they run on the registry's own settings:

    pytest --ds=chatddx.repo.tests.settings src/chatddx/core/tests/test_provisioning.py
"""

from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.core.repl import Repl
from chatddx.dx.fake_vllm import FakeTransport
from chatddx.history.models import RunModel, SessionModel, TrialModel
from chatddx.manage import app
from chatddx.repo.bundles import entity_of
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.names import short_fingerprint
from chatddx.repo.parsers.inventory import parse
from chatddx.repo.shufflers.inventory import owned_inventory
from chatddx.repo.todo import all_entities

pytestmark = pytest.mark.django_db

ARCHIVE = settings.ARCHIVE_IDENTITY_NAME
INVENTORY = settings.INVENTORY_PATH / "inventory.toml"
GIFTBAG = settings.INVENTORY_PATH / "giftbag-inventory.toml"

NOTHING: dict[str, set[str]] = {entity: set() for entity in all_entities}

# what wipe-data says of a user with no history
NO_HISTORY = [
    "[run]: removed 0, unshared 0",
    "[message]: removed 0",
    "[session]: removed 0, unshared 0",
    "[trial]: removed 0, unshared 0",
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
        for entity in all_entities
        for name, (trail, _) in getattr(parsed, entity).items()
    ]


def names(parsed: ParsedInventory) -> dict[str, set[str]]:
    """The names of the records of `parsed`, by entity."""
    return {entity: set(getattr(parsed, entity)) for entity in all_entities}


def owned(owner_name: str) -> dict[str, set[str]]:
    """The names of the branches `owner_name` owns, by entity."""
    inventory = owned_inventory(owner_name)
    return {entity: set(inventory[entity]) for entity in all_entities}


def shared_with(identity_name: str) -> dict[str, set[str]]:
    """The names of the branches `identity_name` collaborates on, by entity."""
    return {
        entity: set(
            entity_of(entity)
            .branch_model.objects.filter(collaborators__name=identity_name)
            .values_list("name", flat=True)
        )
        for entity in all_entities
    }


def versions() -> dict[str, int]:
    """How many versions there are of every entity's branches."""
    return {
        entity: entity_of(entity).branch_model.objects.count()
        for entity in all_entities
    }


# ------------------------------------------------------------------ init-data


def test_init_data_archives_the_inventory_and_shares_it():
    inventory = parse(INVENTORY)

    assert run("init-data", "alex") == receipts(inventory, "archive", "created")

    archived = owned_inventory(ARCHIVE)

    for entity in all_entities:
        for name, (trail, _) in getattr(inventory, entity).items():
            branch_model = archived[entity][name]

            assert branch_model.target.fingerprint == trail.fingerprint
            assert [c.name for c in branch_model.collaborators.all()] == ["alex"]

    # the archive holds the inventory and nothing beside it, and the user
    # holds nothing of their own
    assert owned(ARCHIVE) == names(inventory)
    assert owned("alex") == NOTHING


def test_init_data_again_changes_nothing():
    inventory = parse(INVENTORY)
    _ = run("init-data", "alex")
    before = versions()

    assert run("init-data", "alex") == receipts(inventory, "archive", "validated")
    assert versions() == before
    assert shared_with("alex") == names(inventory)


def test_init_data_shares_the_archive_with_each_user():
    inventory = parse(INVENTORY)

    _ = run("init-data", "alex")
    _ = run("init-data", "other")

    assert shared_with("alex") == names(inventory)
    assert shared_with("other") == names(inventory)


def test_init_data_with_giftbag_gives_the_user_their_own():
    inventory = parse(INVENTORY)
    giftbag = parse(GIFTBAG)

    assert run("init-data", "alex", "--with-giftbag") == (
        receipts(inventory, "archive", "created")
        + receipts(giftbag, "giftbag", "created")
    )

    # the configurations, what they name, and the cases; machines, models and
    # stacks stay the archive's
    assert owned("alex") == names(giftbag)
    assert owned("alex")["stack"] == set()

    # the user's own branches of the archive's content: the same trails
    mine = owned_inventory("alex")
    archived = owned_inventory(ARCHIVE)

    for entity in all_entities:
        for name, branch_model in mine[entity].items():
            assert branch_model.target_id == archived[entity][name].target_id

    # and what the giftbag says beside the content, as the user's
    plan = mine["configuration"]["plan"]
    tags = [(tag.owner.name, tag.entity, tag.name) for tag in plan.tags.all()]
    assert tags == [("alex", "configuration", "ddx")]


def test_init_data_keeps_the_archive_shared_as_it_changes(tmp_path: Path):
    path = tmp_path / "inventory.toml"

    def write(description: str) -> ParsedInventory:
        _ = path.write_text(
            f'[tool.lookup]\nname = "lookup"\ndescription = "{description}"\n'
        )
        return parse(path)

    _ = write("Look it up.")
    _ = run("init-data", "alex", "--inventory", str(path))
    _ = run("init-data", "other", "--inventory", str(path))

    changed = write("Look it up, and say where.")

    assert run("init-data", "alex", "--inventory", str(path)) == receipts(
        changed, "archive", "created"
    )

    # the new version is shared with whoever the one it supersedes was
    lookup = owned_inventory(ARCHIVE)["tool"]["lookup"]
    assert lookup.version_count == 2
    assert [c.name for c in lookup.collaborators.all()] == ["alex", "other"]


def test_init_data_reads_both_inventories_before_writing(tmp_path: Path):
    giftbag = tmp_path / "giftbag.toml"
    _ = giftbag.write_text('[tool.lookup]\nname = "lookup"\ncolour = "blue"\n')

    result = CliRunner().invoke(
        app,
        ["init-data", "alex", "--with-giftbag", "--giftbag-inventory", str(giftbag)],
    )

    assert result.exit_code == 1
    assert result.stderr.startswith(f"{giftbag}: tool 'lookup': unknown key 'colour'")

    # the archive's inventory is sound, and still nothing of it is committed
    assert owned(ARCHIVE) == NOTHING
    assert not IdentityModel.objects.filter(name="alex").exists()


# ------------------------------------------------------------------ wipe-data


def test_wipe_data_takes_back_what_init_data_gave():
    inventory = parse(INVENTORY)
    giftbag = parse(GIFTBAG)
    _ = run("init-data", "alex", "--with-giftbag")
    _ = run("init-data", "other", "--with-giftbag")

    assert run("wipe-data", "alex") == NO_HISTORY + [
        f"[{entity}]: removed {len(getattr(giftbag, entity))}, "
        + f"unshared {len(getattr(inventory, entity))}"
        for entity in all_entities
    ]

    assert owned("alex") == NOTHING
    assert shared_with("alex") == NOTHING

    # what isn't the user's stays: the archive, and another user's own and
    # their share of it
    assert owned(ARCHIVE) == names(inventory)
    assert owned("other") == names(giftbag)
    assert shared_with("other") == names(inventory)


def test_init_data_after_wipe_data_provisions_again():
    inventory = parse(INVENTORY)
    giftbag = parse(GIFTBAG)
    _ = run("init-data", "alex", "--with-giftbag")
    _ = run("wipe-data", "alex")

    # the archive is as it was, and the user's own is made anew
    assert run("init-data", "alex", "--with-giftbag") == (
        receipts(inventory, "archive", "validated")
        + receipts(giftbag, "giftbag", "created")
    )
    assert shared_with("alex") == names(inventory)
    assert owned("alex") == names(giftbag)


def test_wipe_data_of_nobody_removes_nothing():
    assert run("wipe-data", "nobody") == NO_HISTORY + [
        f"[{entity}]: removed 0, unshared 0" for entity in all_entities
    ]
    assert not IdentityModel.objects.filter(name="nobody").exists()


def ran_test_tools(user: str) -> None:
    """A run of test-tools, on the user's own tools, written down."""
    case = next(iter(parse(INVENTORY).case))
    repl = Repl(user, Console(record=True, width=200), transport=FakeTransport())

    assert repl.handle("cell test-tools qwen3-8b-awq@fake")
    assert repl.handle(f"run {case}")
    assert "recorded as run 1" in repl.console.export_text()


def test_wipe_data_takes_back_the_user_s_history_too():
    _ = run("init-data", "alex", "--with-giftbag")
    ran_test_tools("alex")

    # the run read alex's own tools, and goes before them
    assert run("wipe-data", "alex")[:4] == [
        "[run]: removed 1, unshared 0",
        # a round for each tool, then the answer
        "[message]: removed 6",
        "[session]: removed 1, unshared 0",
        "[trial]: removed 1, unshared 0",
    ]
    assert not RunModel.objects.exists()
    assert not TrialModel.objects.exists()
    assert owned("alex") == NOTHING


def test_wipe_data_keeps_a_user_whose_branches_another_s_run_read():
    giftbag = parse(GIFTBAG)
    _ = run("init-data", "alex", "--with-giftbag")
    _ = run("init-data", "bob")
    ran_test_tools("alex")

    # as if bob had run on alex's tools
    bob = IdentityModel.objects.get(name="bob")
    for model in (RunModel, SessionModel, TrialModel):
        _ = model.objects.update(owner=bob)

    result = CliRunner().invoke(app, ["wipe-data", "alex"])

    assert result.exit_code == 1
    assert "alex is kept: runs of others read its branches" in result.output
    # and nothing is taken
    assert owned("alex") == names(giftbag)
    assert RunModel.objects.count() == 1
