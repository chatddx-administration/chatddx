import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.models import IdentityModel
from chatddx.repo.branch_models import CaseBranchModel, ExpectBranchModel
from chatddx.repo.form_data_out import TemplateData
from chatddx.repo.shufflers.scorer import dump_scorer


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
    template_data: TemplateData,
    owner: IdentityModel,
    admin_client: Client,
):
    case_branch = CaseBranchModel.objects.get(owner__name=owner.name, name="case-1")
    scorer_branch, _ = dump_scorer("chatddx.experiment.scorers.exact_match", owner.name)

    case_post_data = template_data.case["case-1"].model_dump(exclude_none=True)
    change_url = reverse("admin:orm_case_change", args=[case_branch.pk])

    get_response = admin_client.get(change_url)
    assert get_response.status_code == 200
    assert b"orm-expectbranchmodel-TOTAL_FORMS" in get_response.content

    post_data = _inline_post_data(
        case_post_data,
        scorer_branch.pk,
        "expected output A",
    )
    response = admin_client.post(change_url, data=post_data, follow=True)
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    expects = list(
        ExpectBranchModel.objects.filter(
            target__case_id=case_branch.target.pk,
        ).order_by("timestamp")
    )
    assert len(expects) == 1
    assert expects[0].target.payload == "expected output A"
    assert expects[0].target.scorer_id == scorer_branch.target.pk
    first_pk = expects[0].pk

    response = admin_client.post(change_url, data=post_data, follow=True)
    assert response.status_code == 200
    expects = list(
        ExpectBranchModel.objects.filter(target__case_id=case_branch.target.pk)
    )
    assert len(expects) == 1
    assert expects[0].pk == first_pk

    messages = [str(m) for m in response.context["messages"]]
    assert any(
        "No changes detected for the" in m and "expectation" in m for m in messages
    )

    edited_post_data = _inline_post_data(
        case_post_data,
        scorer_branch.pk,
        "expected output B",
    )
    response = admin_client.post(change_url, data=edited_post_data, follow=True)
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    all_expects_for_pair = ExpectBranchModel.objects.filter(
        target__case_id=case_branch.target.pk,
        target__scorer_id=scorer_branch.target.pk,
    )
    assert all_expects_for_pair.count() == 2

    response = admin_client.get(change_url)
    assert response.status_code == 200
    assert b"expected output B" in response.content
    assert b"expected output A" not in response.content
