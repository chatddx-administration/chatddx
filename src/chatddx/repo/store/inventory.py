from typing import Any, Literal, cast

from chatddx.repo.entity_names import ENTITY_NAMES, EntityName
from chatddx.repo.families.pydantic import BranchDetails
from chatddx.repo.inventories import (
    InventoryBranchModel,
    InventoryBranchOut,
    InventoryFormDataOut,
    InventoryTrailIn,
    ParsedInventory,
)
from chatddx.repo.store.branch import commit, select_branch_models

type InventoryCommitReceipt = dict[EntityName, dict[str, bool]]


def owned_inventory(
    owner_name: str,
    index_key: Literal["branch_name", "trail_id"] = "branch_name",
) -> InventoryBranchModel:
    """
    Get inventory of branch-canons owned by `owner_name` as an `InventoryBranchModel`
    Dictionary keys kan be either name or pk.
    """
    inventory: dict[str, Any] = {}

    for entity_name in ENTITY_NAMES:
        inventory[entity_name] = {}

        branch_models = select_branch_models(
            entity_name=entity_name,
            owner_name=owner_name,
        )

        for branch_model in branch_models:
            index = {
                "branch_name": branch_model.name,
                "trail_id": str(branch_model.target.pk),
            }[index_key]

            inventory[entity_name][index] = branch_model

    return cast(InventoryBranchModel, cast(object, inventory))


def commit_parsed_inventory(inventory: ParsedInventory) -> InventoryCommitReceipt:
    """
    Commit a parsed inventory to database and use the attached BranchDetails.

    Returns a bool for each branch in the inventory
    True: the head was updated
    False: the trail was already the head
    """

    return {
        entity: {
            name: commit(
                trail=trail,
                branch_details=branch_details,
            )
            for name, (trail, branch_details) in getattr(inventory, entity).items()
        }
        for entity in ENTITY_NAMES
    }


def commit_trails_in(
    inventory: InventoryTrailIn,
    owner_name: str,
) -> InventoryCommitReceipt:
    """
    Commit an inventory of trail schemas to database.
    Use dict-keys as branch name and passed owner_name as owner name.

    Returns a bool for each branch in the inventory
    True: the head was updated
    False: the trail was already the head
    """

    return {
        entity: {
            name: commit(
                trail=trail,
                branch_details=BranchDetails(name=name, owner=owner_name),
            )
            for name, trail in getattr(inventory, entity).items()
        }
        for entity in ENTITY_NAMES
    }


def trails_in(parsed_inventory: ParsedInventory) -> InventoryTrailIn:
    inventory: dict[str, Any] = {
        entity: {
            name: trail
            for name, (trail, _) in getattr(parsed_inventory, entity).items()
        }
        for entity in ENTITY_NAMES
    }
    return InventoryTrailIn.model_validate(inventory)


def form_data_out(branches: InventoryBranchOut) -> InventoryFormDataOut:
    """
    Validate a spec model inventory into a form_data_out inventory.

    A form shows a branch flat: its trail's fields and its details beside its
    name, with the trail's id as the template it was made from. The trail is
    kept whole under `target` too, for a field a form renames: a tool's own
    name, which a form can't call `name`.
    """
    inventory = {}

    for entity_name in ENTITY_NAMES:
        inventory[entity_name] = {}
        for branch_name, branch_out in getattr(
            branches, entity_name
        ).items():
            branch = branch_out.model_dump(mode="json")
            inventory[entity_name][branch_name] = (
                branch["target"]
                | branch["details"]
                | {"name": branch["name"], "target": branch["target"]}
            )

    return InventoryFormDataOut.model_validate(inventory)
