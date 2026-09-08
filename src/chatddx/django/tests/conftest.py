"""Shared fixtures for the admin form/timeline tests in this package.

test_diagnose_api.py and network/test_diagnose_api.py define their own
narrower owner/branch_registry fixtures and are unaffected by these.
"""

from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
from django.contrib.auth.models import User

from chatddx.core.models import IdentityModel
from chatddx.repo.branch_models import BranchModelRegistry
from chatddx.repo.form_data_out import TemplateData
from chatddx.repo.shufflers.main import dump_trail_registry, load_form_data


@pytest.fixture(autouse=True)
def branch_registry(owner: IdentityModel) -> BranchModelRegistry:
    path = Path(__file__).parent / "data/test-registry.toml"
    return dump_trail_registry(path, owner_name=owner.name)


@pytest.fixture
def owner(admin_user: User) -> IdentityModel:
    owner, _created = IdentityModel.objects.get_or_create(name=admin_user.username)
    return owner


@pytest.fixture
def collaborators() -> list[IdentityModel]:
    owner1, _created = IdentityModel.objects.get_or_create(name="alex")
    owner2, _created = IdentityModel.objects.get_or_create(name="olof")
    return [owner1, owner2]


@pytest.fixture
def template_data(branch_registry: BranchModelRegistry) -> TemplateData:
    form_data: dict[str, Any] = defaultdict(dict)

    for bundle, branches in branch_registry.items():
        for branch_model in branches.values():
            form_data[bundle][branch_model.name] = load_form_data(branch_model)

    return TemplateData.model_validate(form_data)


@pytest.fixture
def superagent_post_data(template_data: TemplateData) -> dict[str, Any]:
    post_data_relations: dict[str, dict[str, Any]] = {
        "connection_": template_data.connection["some-connection"].model_dump(
            exclude_none=True
        ),
        "sampling_params_": template_data.sampling_params[
            "some-sampling_params"
        ].model_dump(exclude_none=True),
        "tool_group_": template_data.tool_group["some-tool_group"].model_dump(
            exclude_none=True
        ),
        "output_type_": template_data.output_type["some-output_type"].model_dump(
            exclude_none=True
        ),
    }
    return template_data.agent["some-agent"].model_dump(exclude_none=True) | {
        f"{outer}{inner}": value
        for outer, inner_dict in post_data_relations.items()
        for inner, value in inner_dict.items()
    }
