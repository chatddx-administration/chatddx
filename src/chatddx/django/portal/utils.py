from typing import Any

from django.urls import reverse
from django.utils.html import format_html

from chatddx.repo.bundles import entity_of, view_of
from chatddx.repo.families.django import BranchModel
from chatddx.repo.families.pydantic import BranchSpec, TrailSpec
from chatddx.repo.inventories import InventoryBranchSpec
from chatddx.repo.shufflers import inventory
from chatddx.repo.utils import resolve_trail


def inventory_form_data_out(owner_name: str) -> str:
    inventory_form_data_out = inventory.form_data_out(
        InventoryBranchSpec.model_validate(
            inventory.owned_inventory(owner_name, index_key="trail_id")
        )
    )
    return inventory_form_data_out.model_dump_json(by_alias=True)


def load_form_data(
    branch: BranchModel | BranchSpec[TrailSpec],
) -> dict[str, Any]:

    match branch:
        case BranchModel():
            branch.target = resolve_trail(branch.target)
            branch_spec = entity_of(branch).branch_spec.model_validate(branch)
        case BranchSpec():
            branch_spec = branch

    branch_dict = branch_spec.model_dump()

    form_data = view_of(branch).form_data_out.model_validate(
        branch_dict | branch_dict["target"]
    )
    return form_data.model_dump(by_alias=True)


def truncate_for_list_display(text: str | None, limit: int = 50) -> str:
    limit = min(limit, 50)

    if not text:
        return ""
    if len(text) <= limit:
        return text

    truncated = text[:limit]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated.rstrip() + "…"


def get_branch_link(obj: BranchModel, field_name: str):
    branch_id = getattr(obj, f"{field_name}_id")
    branch_name = getattr(obj, f"{field_name}_name")
    target = getattr(obj.target, field_name)
    label = branch_name or target.fingerprint[:6]
    if branch_id:
        url = (
            reverse(
                f"admin:orm_{field_name.replace('_', '')}_change",
                args=[branch_id],
            )
            + f"?from_agent={obj.pk}"
        )
    else:
        url = (
            reverse(
                f"admin:orm_{field_name.replace('_', '')}_add",
            )
            + f"?from_agent={obj.pk}&target={target.id}"
        )

    return format_html('<a href="{}">{}</a>', url, label)
