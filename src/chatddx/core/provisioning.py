from pathlib import Path
from typing import Annotated

import django
import typer

from chatddx.core import settings

django.setup()
from chatddx.core.utils import ensure_identity
from chatddx.repo.bundles import bundle_of
from chatddx.repo.families.pydantic import BranchDetailsPatch
from chatddx.repo.parsers.inventory import parse
from chatddx.repo.shufflers import inventory
from chatddx.repo.todo import all_entities

receipt_text = {
    True: "created",
    False: "validated",
}


def wipe_data(
    user_name: Annotated[str, typer.Argument()],
):
    user = ensure_identity(user_name)
    for entity in all_entities:
        shared_field = f"shared_{entity.replace('_', '')}branchmodel"

        d, _ = bundle_of(entity).branch_model.objects.filter(owner=user).delete()
        msg = f"[{entity}]: removed {d}"

        if hasattr(user, shared_field):
            rel = getattr(user, shared_field)
            rels = rel.all().count()
            rel.clear()
            msg += f", unshared {rels}"
        print(msg)


def init_data(
    user_name: Annotated[str, typer.Argument()],
    inventory_path: Annotated[
        Path,
        typer.Option(
            "--inventory",
            file_okay=True,
            dir_okay=False,
            exists=True,
            help="location of inventory",
        ),
    ] = settings.INVENTORY_PATH / "inventory.toml",
    with_giftbag: Annotated[
        bool,
        typer.Option(
            "--with-giftbag",
            help="Also dump --giftbag-inventory and add it to OWNER.",
        ),
    ] = False,
    giftbag_inventory_path: Annotated[
        Path,
        typer.Option(
            "--giftbag-inventory",
            file_okay=True,
            dir_okay=False,
            exists=True,
            help="location of the giftbag inventory",
        ),
    ] = settings.INVENTORY_PATH / "giftbag-inventory.toml",
):
    archive = ensure_identity(settings.ARCHIVE_IDENTITY_NAME)
    user = ensure_identity(user_name)

    parsed_archive = parse(inventory_path, BranchDetailsPatch(owner=archive.name))

    archive_commit_receipt = inventory.commit_parsed_inventory(parsed_archive)

    inventory_branch_models = inventory.owned_inventory(archive.name)

    for entity in all_entities:
        for key, receipt in archive_commit_receipt[entity].items():
            branch_model = inventory_branch_models[entity][key]

            branch_model.collaborators.add(user)  # pyright: ignore[reportUnknownMemberType]
            print(
                f"[archive {entity}]: {branch_model.name} ({receipt_text[receipt]} {branch_model.target.fingerprint[:6]})"
            )

    if not with_giftbag:
        return

    parsed_giftbag = parse(giftbag_inventory_path, BranchDetailsPatch(owner=user.name))
    giftbag_commit_receipt = inventory.commit_parsed_inventory(parsed_giftbag)

    for entity in all_entities:
        for key, receipt in giftbag_commit_receipt[entity].items():
            branch_model = inventory_branch_models[entity][key]

            print(
                f"[giftbag {entity}]: {branch_model.name} ({receipt_text[receipt]} {branch_model.target.fingerprint[:6]})"
            )
