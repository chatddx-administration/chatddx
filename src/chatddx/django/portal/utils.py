from typing import Any, cast

from django.db.models import Model

from chatddx.django.portal.links import add_link, change_link, named
from chatddx.repo.bundles import entity_of, view_of
from chatddx.repo.families.django import BranchModel
from chatddx.repo.families.pydantic import BranchSpec, TrailSpec
from chatddx.repo.inventories import InventoryBranchSpec
from chatddx.repo.registry import EntityName
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


def get_branch_link(obj: BranchModel, field_name: EntityName):
    """
    What an agent points at for one of its relations, as a link.

    The page that opens is the viewer's own branch of that trail, or -- when
    they have none -- a form to start one, seeded from the trail the agent
    actually names.
    """
    # Annotated onto the queryset by qs_super_agent (see django/orm/qs.py).
    branch_id = getattr(obj, f"{field_name}_id")
    branch_name = getattr(obj, f"{field_name}_name")

    # Every registered proxy mixes BranchProxy into a branch model; the
    # mixin is what the registry is typed by, so the model half needs saying.
    proxy = cast(type[Model], view_of(field_name).proxy)
    trail = named(getattr(obj.target, field_name), branch_name)

    if branch_id:
        return change_link(proxy(pk=branch_id), trail, from_agent=obj.pk)

    return add_link(proxy, trail, from_agent=obj.pk, target=trail.id)
