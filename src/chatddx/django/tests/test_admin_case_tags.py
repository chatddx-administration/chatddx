import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.models import IdentityModel, TagModel
from chatddx.repo.branch_models import CaseBranchModel
from chatddx.repo.form_data_out import TemplateData


@pytest.mark.django_db
def test_case_tags_create_edit_remove_and_messages(
    template_data: TemplateData,
    owner: IdentityModel,
    admin_client: Client,
):
    case_branch = CaseBranchModel.objects.get(owner__name=owner.name, name="case-1")
    change_url = reverse("admin:orm_case_change", args=[case_branch.pk])

    prefix = "orm-expectbranchmodel"
    post_data = template_data.case["case-1"].model_dump(exclude_none=True) | {
        f"{prefix}-TOTAL_FORMS": "0",
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    assert post_data.get("tags") == []

    response = admin_client.post(change_url, data=post_data, follow=True)
    assert response.status_code == 200
    (message,) = [str(m) for m in response.context["messages"]]
    assert "No changes detected" in message

    response = admin_client.post(
        change_url, data=post_data | {"tags": ["clinical"]}, follow=True
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    messages = [str(m) for m in response.context["messages"]]
    assert "Case payload unchanged, but tags were changed." in messages

    tag = TagModel.objects.get(name="clinical")
    case_branch.refresh_from_db()
    assert list(case_branch.tags.all()) == [tag]

    get_response = admin_client.get(change_url)
    assert get_response.status_code == 200
    assert get_response.context["adminform"].form.initial["tags"] == [tag.pk]

    response = admin_client.post(
        change_url, data=post_data | {"tags": [str(tag.pk)]}, follow=True
    )
    assert response.status_code == 200
    (message,) = [str(m) for m in response.context["messages"]]
    assert "No changes detected" in message

    response = admin_client.post(change_url, data=post_data, follow=True)
    assert response.status_code == 200
    messages = [str(m) for m in response.context["messages"]]
    assert "Case payload unchanged, but tags were changed." in messages

    case_branch.refresh_from_db()
    assert list(case_branch.tags.all()) == []


@pytest.mark.django_db
def test_case_tags_are_scoped_to_owner(
    template_data: TemplateData,
    owner: IdentityModel,
    admin_client: Client,
):
    other_owner, _ = IdentityModel.objects.get_or_create(name="olof")
    other_tag = TagModel.objects.create(name="clinical", owner=other_owner)

    case_branch = CaseBranchModel.objects.get(owner__name=owner.name, name="case-1")
    change_url = reverse("admin:orm_case_change", args=[case_branch.pk])

    get_response = admin_client.get(change_url)
    tags_field = get_response.context["adminform"].form.fields["tags"]
    assert other_tag not in tags_field.queryset

    prefix = "orm-expectbranchmodel"
    post_data = template_data.case["case-1"].model_dump(exclude_none=True) | {
        f"{prefix}-TOTAL_FORMS": "0",
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }

    response = admin_client.post(
        change_url, data=post_data | {"tags": ["clinical"]}, follow=True
    )
    assert response.status_code == 200

    own_tag = TagModel.objects.get(name="clinical", owner=owner)
    assert own_tag.pk != other_tag.pk

    case_branch.refresh_from_db()
    assert list(case_branch.tags.all()) == [own_tag]
