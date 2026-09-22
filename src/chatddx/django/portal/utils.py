import json
from typing import Any, Literal

from chatddx.django.orm.qs import qs_canon, qs_with_details
from chatddx.repo.bundles import entity_of, view_of
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.families.pydantic import BranchSpec, TrailSpec
from chatddx.repo.utils import resolve_trails


def load_form_data(
    branch: BranchModel | BranchSpec[TrailSpec],
    mode: Literal["python", "json"] = "python",
) -> dict[str, Any]:
    match branch:
        case BranchModel():
            branch.target = resolve_trails([branch.target])[0]
            branch_spec = entity_of(branch).branch_spec.model_validate(branch)
        case BranchSpec():
            branch_spec = branch

    branch_dict = branch_spec.model_dump()

    form_data = view_of(branch).form_data_out.model_validate(
        branch_dict | branch_dict["target"]
    )
    return form_data.model_dump(mode=mode, by_alias=True)


def template_registry(owner_name: str, entities: tuple[EntityName, ...]) -> str:
    return json.dumps(
        {entity: _entity_registry(entity, owner_name) for entity in entities}
    )


def _entity_registry(entity: EntityName, owner_name: str) -> dict[str, Any]:
    branches = list(
        qs_with_details(
            qs_canon(entity_of(entity).branch_model.objects.all(), owner_name)
        )
    )

    _ = resolve_trails([branch.target for branch in branches])

    return {
        str(branch.target_id): load_form_data(branch, mode="json")
        for branch in branches
    }


def template_choices(
    model_cls: type[BranchModel],
    owner_name: str,
) -> list[tuple[str, str]]:
    owned = qs_canon(model_cls.objects.all(), owner_name)

    return [("", "--- clear ---")] + [
        (str(target_id), name)
        for target_id, name in owned.values_list("target_id", "name")
    ]


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
