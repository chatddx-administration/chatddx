from pathlib import Path
from typing import Annotated, Any

import django
import typer

from chatddx.core import settings

django.setup()
from django.db import transaction
from django.db.models import ProtectedError, QuerySet

from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identity
from chatddx.history.models import (
    ConversationModel,
    MessageModel,
    RunModel,
    ScoreModel,
    TrialModel,
)
from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import ENTITY_NAMES, EntityName
from chatddx.repo.families.pydantic import BranchDetailsPatch
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.names import short_fingerprint
from chatddx.repo.parsers.inventory import ParseError, parse
from chatddx.repo.queries import qs_head
from chatddx.repo.store import inventory
from chatddx.worker.models import JobModel

receipt_text = {
    True: "created",
    False: "validated",
}


def wipe_data(
    user_name: Annotated[str, typer.Argument()],
):
    # all of it or none: what another user's history read stays
    try:
        with transaction.atomic():
            lines = _wipe_history(user_name) + _wipe_branches(user_name)
    except ProtectedError as e:
        typer.echo(
            f"{user_name} is kept: others' runs or scores read its branches", err=True
        )
        raise typer.Exit(1) from e

    for line in lines:
        print(line)


def _wipe_history(user_name: str) -> list[str]:
    """
    The jobs the user's batches gave the worker, their scores and runs, the
    conversations their messages were in, and the trials no one else's run
    is left of.
    """
    # what refers to a row goes before the row
    jobs = _removed(JobModel.objects.filter(owner__name=user_name))
    scores = _removed(ScoreModel.objects.filter(owner__name=user_name))
    runs = _removed(RunModel.objects.filter(owner__name=user_name))
    messages = _removed(
        MessageModel.objects.filter(conversation__owner__name=user_name)
    )
    conversations = _removed(ConversationModel.objects.filter(owner__name=user_name))
    trials = _removed(TrialModel.objects.filter(runs__isnull=True))

    return [
        f"[job]: removed {jobs}",
        f"[score]: removed {scores}",
        f"[run]: removed {runs}, unshared {_unshared(RunModel, user_name)}",
        f"[message]: removed {messages}",
        f"[conversation]: removed {conversations}, "
        + f"unshared {_unshared(ConversationModel, user_name)}",
        f"[trial]: removed {trials}",
    ]


def _removed(qs: QuerySet[Any]) -> int:
    _, removed = qs.delete()
    return removed.get(qs.model._meta.label, 0)


def _unshared(model: type[RunModel | ConversationModel], user_name: str) -> int:
    unshared, _ = model.collaborators.through.objects.filter(
        identitymodel__name=user_name
    ).delete()
    return unshared


def _wipe_branches(user_name: str) -> list[str]:
    lines: list[str] = []

    for entity in ENTITY_NAMES:
        branch_model = entity_of(entity).branch_model

        _, removed = branch_model.objects.filter(owner__name=user_name).delete()
        unshared, _ = branch_model.collaborators.through.objects.filter(
            identitymodel__name=user_name
        ).delete()

        lines.append(
            f"[{entity}]: removed {removed.get(branch_model._meta.label, 0)}, "
            + f"unshared {unshared}"
        )

    return lines


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
    # Both are read before either is written, so a mistake in one commits
    # nothing of the other.
    archived = _parse(inventory_path, settings.ARCHIVE_IDENTITY_NAME)
    giftbag = _parse(giftbag_inventory_path, user_name) if with_giftbag else None

    user = ensure_identity(user_name)
    archive_receipt = _commit("archive", archived)

    # The archive keeps the inventory, and its users collaborate on it.
    for entity in ENTITY_NAMES:
        _share(entity, list(archive_receipt[entity]), user)

    if giftbag is not None:
        _ = _commit("giftbag", giftbag)


def _share(entity: EntityName, names: list[str], user: IdentityModel) -> None:
    """The heads of the archive's branches of `names`, shared with `user`."""
    if not names:
        return

    branch_model = entity_of(entity).branch_model
    heads = qs_head(
        branch_model.objects.filter(name__in=names), settings.ARCHIVE_IDENTITY_NAME
    )
    through = branch_model.collaborators.through
    shared = f"{branch_model._meta.model_name}_id"

    _ = through.objects.bulk_create(
        [
            through(**{shared: head, "identitymodel_id": user.pk})
            for head in heads.values_list("id", flat=True)
        ],
        ignore_conflicts=True,
    )


def _parse(path: Path, owner_name: str) -> ParsedInventory:
    try:
        return parse(path, BranchDetailsPatch(owner=owner_name))
    except ParseError as e:
        typer.echo(f"{path}: {e}", err=True)
        raise typer.Exit(1) from None


def _commit(label: str, parsed: ParsedInventory) -> inventory.InventoryCommitReceipt:
    receipt = inventory.commit_parsed_inventory(parsed)

    for entity in ENTITY_NAMES:
        for name, (trail, _) in getattr(parsed, entity).items():
            print(
                f"[{label} {entity}]: {name} ({receipt_text[receipt[entity][name]]} "
                + f"{short_fingerprint(trail.fingerprint)})"
            )

    return receipt
