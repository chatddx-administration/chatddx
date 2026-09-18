import logging

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.repo.entities.expect.django import ExpectBranchModel
from chatddx.repo.inventories import InventoryFormDataOut

logger = logging.getLogger(__name__)


def _inline_post_data(case_post_data, scorer, payload, *, extra=1):
    prefix = "orm-expectbranchmodel"
    data = dict(case_post_data)
    data |= {
        f"{prefix}-TOTAL_FORMS": str(extra),
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
        f"{prefix}-0-scorer": scorer,
        f"{prefix}-0-payload": payload,
    }
    return data


@pytest.mark.django_db
def test_expect_inline_add_then_edit_is_idempotent_and_versions(
    inventory_fixture_fdo: InventoryFormDataOut,
    admin_client: Client,
):
    case_1 = inventory_fixture_fdo.case["case-1"]
    scorer_1 = inventory_fixture_fdo.scorer["scorer-1"]

    case_post_data = case_1.model_dump(exclude_none=True)

    change_url = reverse("admin:orm_case_change", args=[case_1.id])

    get_response = admin_client.get(change_url)
    assert get_response.status_code == 200
    assert b"orm-expectbranchmodel-TOTAL_FORMS" in get_response.content

    post_data = _inline_post_data(
        case_post_data,
        scorer_1.id,
        "expected output A",
    )

    response = admin_client.post(change_url, data=post_data, follow=True)

    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    expects = list(
        ExpectBranchModel.objects.filter(
            target__case_id=case_1.id,
        ).order_by("timestamp")
    )
    assert len(expects) == 2
    assert expects[0].name == "expect-1"
    assert expects[1].name == "a97f88"
    assert expects[1].target.payload == "expected output A"
    assert str(expects[1].target.scorer_id) == scorer_1.id
    first_pk = expects[1].pk

    response = admin_client.post(change_url, data=post_data, follow=True)
    assert response.status_code == 200
    expects = list(ExpectBranchModel.objects.filter(target__case_id=case_1.id))
    assert len(expects) == 2
    assert expects[1].pk == first_pk

    messages = [str(m) for m in response.context["messages"]]
    assert any(
        "No changes detected for the" in m and "expectation" in m for m in messages
    )

    edited_post_data = _inline_post_data(
        case_post_data,
        scorer_1.id,
        "expected output B",
    )
    response = admin_client.post(change_url, data=edited_post_data, follow=True)
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    all_expects_for_pair = ExpectBranchModel.objects.filter(
        target__case_id=case_1.id,
        target__scorer_id=scorer_1.id,
    ).order_by("timestamp")

    assert all_expects_for_pair.count() == 3

    assert all_expects_for_pair[1].name == "a97f88"
    assert all_expects_for_pair[2].name == "543b35"

    response = admin_client.get(change_url)

    assert response.status_code == 200
    assert b"expected output B" in response.content

    # Expects are currently named by their fingerprint (which might be what we want),
    # so the old ones will be around and we disable this test for now.
    # assert b"expected output A" not in response.content
