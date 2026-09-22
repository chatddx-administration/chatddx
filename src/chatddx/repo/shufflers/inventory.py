from typing import Any, Literal, cast

from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.pydantic import BranchSchemaDetails
from chatddx.repo.inventories import (
    InventoryBranchModel,
    InventoryBranchSpec,
    InventoryFormDataOut,
    InventoryTrailSchema,
    ParsedInventory,
)
from chatddx.repo.shufflers.branch import commit, select_branch_models
from chatddx.repo.todo import all_entities

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

    for entity_name in all_entities:
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
    True: canon was updated
    False: trail schema was already canon
    """

    return {
        entity: {
            name: commit(
                trail=trail,
                branch_details=branch_details,
            )
            for name, (trail, branch_details) in getattr(inventory, entity).items()
        }
        for entity in all_entities
    }


def commit_trail_schemas(
    inventory: InventoryTrailSchema,
    owner_name: str,
) -> InventoryCommitReceipt:
    """
    Commit an inventory of trail schemas to database.
    Use dict-keys as branch name and passed owner_name as owner name.

    Returns a bool for each branch in the inventory
    True: canon was updated
    False: trail schema was already canon
    """

    return {
        entity: {
            name: commit(
                trail=trail,
                branch_details=BranchSchemaDetails(name=name, owner=owner_name),
            )
            for name, trail in getattr(inventory, entity).items()
        }
        for entity in all_entities
    }


def trail_schema(parsed_inventory: ParsedInventory) -> InventoryTrailSchema:
    inventory: dict[str, Any] = {
        entity: {
            name: trail
            for name, (trail, _) in getattr(parsed_inventory, entity).items()
        }
        for entity in all_entities
    }
    return InventoryTrailSchema.model_validate(inventory)


def form_data_out(inventory_fixture_bs: InventoryBranchSpec) -> InventoryFormDataOut:
    """
    Validate a spec model inventory into a form_data_out inventory
    """
    inventory = {}

    for entity_name in all_entities:
        inventory[entity_name] = {}
        for branch_name, branch_spec in getattr(
            inventory_fixture_bs, entity_name
        ).items():
            branch_dict = branch_spec.model_dump()
            inventory[entity_name][branch_name] = branch_dict | branch_dict["target"]

    return InventoryFormDataOut.model_validate(inventory)
