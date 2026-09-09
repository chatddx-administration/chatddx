from collections import defaultdict
from typing import get_args

from django.urls import reverse
from django.utils.html import format_html

from chatddx.core.django_fields import resolve_related_array_fields
from chatddx.repo.base import BaseFormDataOut, BranchModel, BranchSpec
from chatddx.repo.form_data_out import TemplateData
from chatddx.repo.main import BundleName, Repo
from chatddx.repo.shufflers.main import load_branches


def load_form_data(
    branch: BranchModel | BranchSpec,
) -> BaseFormDataOut:

    match branch:
        case BranchModel():
            branch.target = resolve_related_array_fields(branch.target)
            branch_spec = Repo(branch, BranchSpec).model_validate(branch)
        case BranchSpec():
            branch_spec = branch

    branch_dict = branch_spec.model_dump()
    form_data = Repo(branch, BaseFormDataOut).model_validate(
        branch_dict | branch_dict["target"]
    )
    return form_data


def load_template_data(owner_name: str):

    payload: dict[BundleName, dict[str, BaseFormDataOut]] = defaultdict(dict)

    for bundle in get_args(BundleName):
        form_data_cls = Repo(bundle, BaseFormDataOut)
        branch_specs = load_branches(bundle, owner_name)

        for branch_spec in branch_specs:
            branch_dict = branch_spec.model_dump()
            form_data = branch_dict | branch_dict["target"]
            payload[bundle][str(form_data["id"])] = form_data_cls.model_validate(
                form_data
            )

    return TemplateData.model_validate(payload)


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
