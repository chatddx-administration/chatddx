"""Admin version-history ("timeline") behavior, verified generically across
every branch-backed model: saving is idempotent, renaming forks a new
branch, and the change-view pager reports correct prev/next/version info.

See also test_admin_branch_forms.py (single-model add/change/delete flows)
and test_admin_superagent_form.py (the composite SuperAgent form) for other
admin behavior split out of what used to be this one file.
"""

from typing import Any, Callable

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.models import IdentityModel
from chatddx.repo import proxies
from chatddx.repo.form_data_out import TemplateData

parameters: list[
    tuple[
        str,
        str,
        Any,
        Callable[[int], str | int],
    ]
] = [
    (
        "agent",
        "instructions",
        proxies.Agent,
        lambda i: f"instruction {i}",
    ),
    (
        "tool_group",
        "instructions",
        proxies.ToolGroup,
        lambda i: f"instruction {i}",
    ),
    (
        "output_type",
        "definition",
        proxies.OutputType,
        lambda i: f"value={i}",
    ),
    (
        "connection",
        "model",
        proxies.Connection,
        lambda i: f"model {i}",
    ),
    (
        "sampling_params",
        "seed",
        proxies.SamplingParams,
        lambda i: i,
    ),
    (
        "tool",
        "command",
        proxies.Tool,
        lambda i: f"cmd_{i}",
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize("test_model, test_field, model_class, mutator", parameters)
def test_idempotent_save_prevents_duplicates(
    admin_client: Client,
    template_data: TemplateData,
    owner: IdentityModel,
    test_model: str,
    test_field: str,
    model_class: proxies.BranchProxy,
    mutator: Callable[[int], str],
):
    data = getattr(template_data, test_model)
    admin_name = test_model.replace("_", "")

    add_url = reverse(f"admin:orm_{admin_name}_add")

    some_key, *_rest = data.keys()

    response = admin_client.post(
        add_url,
        data=data[some_key].model_dump(by_alias=True, exclude_none=True),
        follow=True,
    )

    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    (message,) = [str(m) for m in response.context["messages"]]
    assert "up to date" in message

    response = admin_client.post(
        add_url,
        data=data[some_key].model_dump(by_alias=True, exclude_none=True),
        follow=True,
    )

    (message,) = [str(m) for m in response.context["messages"]]
    assert "up to date" in message

    timeline = model_class.objects.filter(owner_id=owner.pk, name=some_key)
    assert len(timeline) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("test_model, test_field, model_class, mutator", parameters)
def test_name_change_creates_new_branch(
    admin_client: Client,
    template_data: TemplateData,
    owner: IdentityModel,
    test_model: str,
    test_field: str,
    model_class: proxies.BranchProxy,
    mutator: Callable[[int], str],
):
    data = getattr(template_data, test_model)
    admin_name = test_model.replace("_", "")

    add_url = reverse(f"admin:orm_{admin_name}_add")

    some_key, another_key, *_rest = data.keys()

    data[some_key].name = another_key

    admin_client.post(
        add_url,
        data=data[some_key].model_dump(by_alias=True, exclude_none=True),
        follow=True,
    )
    timeline = model_class.objects.filter(owner_id=owner.pk, name=some_key)
    assert len(timeline) == 1

    timeline = model_class.objects.filter(owner_id=owner.pk, name=another_key)
    assert len(timeline) == 2


@pytest.mark.django_db
@pytest.mark.parametrize("test_model, test_field, model_class, mutator", parameters)
def test_pager_context_navigation(
    admin_client: Client,
    template_data: TemplateData,
    owner: IdentityModel,
    test_model: str,
    test_field: str,
    model_class: proxies.BranchProxy,
    mutator: Callable[[int], str],
):
    data = getattr(template_data, test_model)
    admin_name = test_model.replace("_", "")

    add_url = reverse(f"admin:orm_{admin_name}_add")

    some_key, _another_key, *_rest = data.keys()

    for i in range(3):
        setattr(data[some_key], test_field, mutator(i))
        admin_client.post(
            add_url,
            data=data[some_key].model_dump(by_alias=True, exclude_none=True),
            follow=True,
        )

    versions = list(
        model_class.objects.filter(
            owner_id=owner.pk,
            name=some_key,
        ).order_by("timestamp")
    )

    v2_url = reverse(f"admin:orm_{admin_name}_change", args=[versions[1].pk])
    response = admin_client.get(v2_url)
    assert response.status_code == 200
    assert "prev_" in response.context
    assert "next_" in response.context
    assert response.context["version_info"]["current"] == 2
    assert response.context["version_info"]["total"] == 4

    v1_url = reverse(f"admin:orm_{admin_name}_change", args=[versions[0].pk])
    response = admin_client.get(v1_url)
    assert response.status_code == 200
    assert "next_" in response.context
    assert response.context["version_info"]["current"] == 1
    assert response.context["version_info"]["total"] == 4

    v4_url = reverse(f"admin:orm_{admin_name}_change", args=[versions[3].pk])
    response = admin_client.get(v4_url)
    assert response.status_code == 200
    assert "prev_" in response.context
    assert response.context["version_info"]["current"] == 4
    assert response.context["version_info"]["total"] == 4
