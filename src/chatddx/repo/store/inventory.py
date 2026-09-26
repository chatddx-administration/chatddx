from typing import Any, Literal, cast

from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identity
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
                "trail_id": str(branch_model.trail.pk),
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

    owners = _Owners()

    return {
        entity: {
            name: commit(trail, branch_details, owners[branch_details.owner])
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

    owner = ensure_identity(owner_name)

    return {
        entity: {
            name: commit(trail, BranchDetails(name=name, owner=owner_name), owner)
            for name, trail in getattr(inventory, entity).items()
        }
        for entity in ENTITY_NAMES
    }


class _Owners(dict[str, IdentityModel]):
    """Each owner an inventory names, read the first time it is named."""

    def __missing__(self, name: str) -> IdentityModel:
        self[name] = ensure_identity(name)
        return self[name]


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
    inventory = {}

    for entity_name in ENTITY_NAMES:
        inventory[entity_name] = {}
        for branch_name, branch_out in getattr(branches, entity_name).items():
            branch = branch_out.model_dump(mode="json")
            inventory[entity_name][branch_name] = (
                branch["trail"]
                | branch["details"]
                | {"name": branch["name"], "trail": branch["trail"]}
            )

    return InventoryFormDataOut.model_validate(inventory)
