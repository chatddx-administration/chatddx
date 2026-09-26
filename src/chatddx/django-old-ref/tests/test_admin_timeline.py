import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.models import IdentityModel
from chatddx.django.portal.utils import load_form_data
from chatddx.repo.entities.agent.django import Agent
from chatddx.repo.inventories import InventoryBranchModel, InventoryFormDataOut

pytestmark = [
    pytest.mark.django_db(transaction=True),
]


def test_idempotent_save_prevents_duplicates(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    test_model = "agent"
    model_class = Agent

    data = getattr(inventory_fixture_fdo, test_model)
    admin_name = test_model.replace("_", "")

    add_url = reverse(f"admin:orm_{admin_name}_add")

    some_key, *_rest = data.keys()

    response = user_client.post(
        add_url,
        data=data[some_key].model_dump(by_alias=True, exclude_none=True),
        follow=True,
    )

    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    (message,) = [str(m) for m in response.context["messages"]]
    assert "up to date" in message

    response = user_client.post(
        add_url,
        data=data[some_key].model_dump(by_alias=True, exclude_none=True),
        follow=True,
    )

    (message,) = [str(m) for m in response.context["messages"]]
    assert "up to date" in message

    timeline = model_class.objects.filter(owner_id=owner.pk, name=some_key)
    assert len(timeline) == 1


def test_name_change_creates_new_branch(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    test_model = "agent"
    model_class = Agent

    data = getattr(inventory_fixture_fdo, test_model)
    admin_name = test_model.replace("_", "")

    add_url = reverse(f"admin:orm_{admin_name}_add")

    some_key, another_key, *_rest = data.keys()

    data[some_key].name = another_key

    _ = user_client.post(
        add_url,
        data=data[some_key].model_dump(by_alias=True, exclude_none=True),
        follow=True,
    )
    timeline = model_class.objects.filter(owner_id=owner.pk, name=some_key)
    assert len(timeline) == 1

    timeline = model_class.objects.filter(owner_id=owner.pk, name=another_key)
    assert len(timeline) == 2


def test_pager_context_navigation(
    user_client: Client,
    inventory_fixture_bm: InventoryBranchModel,
    owner: IdentityModel,
):
    test_model = "agent"
    model_class = Agent

    data = load_form_data(inventory_fixture_bm["agent"]["some-agent"])

    admin_name = test_model.replace("_", "")
    add_url = reverse(f"admin:orm_{admin_name}_add")

    for i in range(3):
        data["instruction"] = str(i)
        print(data)
        _ = user_client.post(
            add_url,
            data=data,
            follow=True,
        )

    versions = list(
        model_class.objects.filter(
            owner_id=owner.pk,
            name="some-agent",
        ).order_by("timestamp")
    )

    v2_url = reverse(f"admin:orm_{admin_name}_change", args=[versions[1].pk])
    response = user_client.get(v2_url)
    assert response.status_code == 200
    assert "prev_" in response.context
    assert "next_" in response.context
    assert response.context["version_info"]["current"] == 2
    assert response.context["version_info"]["total"] == 4

    v1_url = reverse(f"admin:orm_{admin_name}_change", args=[versions[0].pk])
    response = user_client.get(v1_url)
    assert response.status_code == 200
    assert "next_" in response.context
    assert response.context["version_info"]["current"] == 1
    assert response.context["version_info"]["total"] == 4

    v4_url = reverse(f"admin:orm_{admin_name}_change", args=[versions[3].pk])
    response = user_client.get(v4_url)
    assert response.status_code == 200
    assert "prev_" in response.context
    assert response.context["version_info"]["current"] == 4
    assert response.context["version_info"]["total"] == 4
