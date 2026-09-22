# pyright: basic
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.models import IdentityModel, TagModel
from chatddx.core.utils import ensure_identity, ensure_tag
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.inventories import InventoryFormDataOut

pytestmark = [
    pytest.mark.django_db(transaction=True),
]

PREFIX = "orm-expect"


def case_post_data(
    inventory_fixture_fdo: InventoryFormDataOut,
    case_name: str = "case-1",
    **overrides: Any,
) -> dict[str, Any]:
    """
    A case change form POST with an empty expect inline, as the browser sends
    it when the case has no expectation rows of its own.
    """
    data = inventory_fixture_fdo.case[case_name].model_dump(exclude_none=True)

    return (
        data
        | {
            f"{PREFIX}-TOTAL_FORMS": "0",
            f"{PREFIX}-INITIAL_FORMS": "0",
            f"{PREFIX}-MIN_NUM_FORMS": "0",
            f"{PREFIX}-MAX_NUM_FORMS": "1000",
        }
        | overrides
    )


def case_branch(owner: IdentityModel, name: str = "case-1") -> CaseBranchModel:
    return CaseBranchModel.objects.filter(owner=owner, name=name).latest("timestamp")


def tag_names(branch: CaseBranchModel) -> list[str]:
    return sorted(branch.tags.values_list("name", flat=True))


def messages_of(response: Any) -> list[str]:
    return [str(message) for message in response.context["messages"]]


def test_the_inventory_tags_are_case_tags_of_their_owner(
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    assert tag_names(case_branch(owner)) == ["tag-1", "tag-2"]

    for name in ("tag-1", "tag-2"):
        tag = TagModel.objects.get(name=name, owner=owner)
        assert tag.entity == "case"


def test_case_tags_are_rendered_as_the_widgets_own_choices(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    case = case_branch(owner)

    response = user_client.get(reverse("admin:orm_case_change", args=[case.pk]))
    assert response.status_code == 200

    form = response.context["adminform"].form
    assert sorted(form.initial["tags"]) == sorted(
        case.tags.values_list("pk", flat=True)
    )
    assert sorted(tag.name for tag in form.fields["tags"].queryset) == [
        "tag-1",
        "tag-2",
    ]


def test_case_tags_are_added_edited_and_removed(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    case = case_branch(owner)
    change_url = reverse("admin:orm_case_change", args=[case.pk])
    kept = TagModel.objects.get(name="tag-1", owner=owner, entity="case")

    response = user_client.post(
        change_url,
        data=case_post_data(inventory_fixture_fdo, tags=[str(kept.pk), "clinical"]),
        follow=True,
    )
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    added = TagModel.objects.get(name="clinical", owner=owner)
    assert added.entity == "case"

    # tags are not the case's content, so the case did not get a new version
    assert CaseBranchModel.objects.filter(owner=owner, name="case-1").count() == 1
    assert tag_names(case_branch(owner)) == ["clinical", "tag-1"]
    assert any("updated tags" in message for message in messages_of(response))

    response = user_client.post(
        change_url,
        data=case_post_data(inventory_fixture_fdo, tags=[str(kept.pk)]),
        follow=True,
    )
    assert tag_names(case_branch(owner)) == ["tag-1"]
    assert any("updated tags" in message for message in messages_of(response))

    response = user_client.post(
        change_url,
        data=case_post_data(inventory_fixture_fdo, tags=[str(kept.pk)]),
        follow=True,
    )
    assert tag_names(case_branch(owner)) == ["tag-1"]
    assert messages_of(response) == [
        "No changes detected. The current version is up to date."
    ]

    response = user_client.post(
        change_url,
        data=case_post_data(inventory_fixture_fdo),
        follow=True,
    )
    assert tag_names(case_branch(owner)) == []
    assert any("updated tags" in message for message in messages_of(response))


def test_a_new_case_version_keeps_the_tags(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    case = case_branch(owner)
    tags = [str(pk) for pk in case.tags.values_list("pk", flat=True)]

    response = user_client.post(
        reverse("admin:orm_case_change", args=[case.pk]),
        data=case_post_data(
            inventory_fixture_fdo,
            payload="case payload 1, rewritten",
            tags=tags,
        ),
        follow=True,
    )
    assert response.status_code == 200

    rewritten = case_branch(owner)
    assert rewritten.pk != case.pk
    assert tag_names(rewritten) == ["tag-1", "tag-2"]

    # and the version it superseded keeps its own
    assert tag_names(case) == ["tag-1", "tag-2"]


def test_a_case_save_leaves_the_relations_the_form_has_no_say_over(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    case = case_branch(owner)
    collaborator = ensure_identity("olof")
    case.collaborators.set([collaborator])

    response = user_client.post(
        reverse("admin:orm_case_change", args=[case.pk]),
        data=case_post_data(inventory_fixture_fdo),
        follow=True,
    )
    assert response.status_code == 200

    # the case form has no collaborators field, which is not the same as
    # saying the case has no collaborators
    assert list(case_branch(owner).collaborators.all()) == [collaborator]


def test_case_tags_are_scoped_to_their_owner(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    other = ensure_identity("olof")
    their_tag = ensure_tag(other, "case", "clinical")

    case = case_branch(owner)
    change_url = reverse("admin:orm_case_change", args=[case.pk])

    response = user_client.get(change_url)
    assert their_tag not in response.context["adminform"].form.fields["tags"].queryset

    # their tag is not even addressable by pk, and typing the name makes mine
    response = user_client.post(
        change_url,
        data=case_post_data(
            inventory_fixture_fdo,
            tags=[str(their_tag.pk), "clinical"],
        ),
        follow=True,
    )
    assert response.status_code == 200

    my_tag = TagModel.objects.get(name="clinical", owner=owner)
    assert my_tag.pk != their_tag.pk
    assert list(case_branch(owner).tags.all()) == [my_tag]


def test_case_tags_are_scoped_to_their_entity(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    agent_tag = ensure_tag(owner, "agent", "clinical")

    case = case_branch(owner)
    change_url = reverse("admin:orm_case_change", args=[case.pk])

    response = user_client.get(change_url)
    assert agent_tag not in response.context["adminform"].form.fields["tags"].queryset

    response = user_client.post(
        change_url,
        data=case_post_data(
            inventory_fixture_fdo,
            tags=[str(agent_tag.pk), "clinical"],
        ),
        follow=True,
    )
    assert response.status_code == 200

    case_tag = TagModel.objects.get(name="clinical", owner=owner, entity="case")
    assert case_tag.pk != agent_tag.pk
    assert list(case_branch(owner).tags.all()) == [case_tag]
