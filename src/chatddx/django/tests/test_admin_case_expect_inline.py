# pyright: basic
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identity
from chatddx.repo.entities.case.django import CaseBranchModel, CaseTrailModel
from chatddx.repo.entities.case.pydantic import CaseTrailSchema
from chatddx.repo.entities.expect.django import ExpectBranchModel
from chatddx.repo.entities.expect.pydantic import ExpectTrailSchema
from chatddx.repo.entities.scorer.django import ScorerBranchModel
from chatddx.repo.entities.scorer.pydantic import ScorerTrailSchema
from chatddx.repo.families.pydantic import BranchSchemaDetails
from chatddx.repo.inventories import InventoryFormDataOut
from chatddx.repo.shufflers.branch import commit

PREFIX = "orm-expect"


def inline_payloads(response: Any) -> list[str]:
    """
    The payloads of the expect rows the change form was rendered with.
    """

    (inline,) = response.context["inline_admin_formsets"]

    return sorted(form.initial["payload"] for form in inline.formset.initial_forms)


def case_post_data(
    inventory_fixture_fdo: InventoryFormDataOut,
    case_name: str,
    *rows: dict[str, Any],
    initial: int = 0,
) -> dict[str, Any]:
    """
    A case change form POST, with `rows` as the expect inline's rows.
    """

    data = inventory_fixture_fdo.case[case_name].model_dump(exclude_none=True)

    data |= {
        f"{PREFIX}-TOTAL_FORMS": str(len(rows)),
        f"{PREFIX}-INITIAL_FORMS": str(initial),
        f"{PREFIX}-MIN_NUM_FORMS": "0",
        f"{PREFIX}-MAX_NUM_FORMS": "1000",
    }

    for index, row in enumerate(rows):
        data |= {f"{PREFIX}-{index}-{key}": value for key, value in row.items()}

    return data


def expect_row(
    payload: str,
    scorer: ScorerBranchModel,
    expect: ExpectBranchModel | None = None,
    delete: bool = False,
) -> dict[str, Any]:
    row: dict[str, Any] = {"payload": payload, "scorer": scorer.pk}

    if expect is not None:
        row["id"] = expect.pk

    if delete:
        row["DELETE"] = "on"

    return row


def case_branch(owner: IdentityModel, name: str = "case-1") -> CaseBranchModel:
    return CaseBranchModel.objects.filter(owner=owner, name=name).latest("timestamp")


def linked_expects(case: CaseBranchModel) -> list[ExpectBranchModel]:
    return list(
        ExpectBranchModel.objects.filter(target__cases=case.pk).order_by("timestamp")
    )


@pytest.fixture
def scorer_c(owner: IdentityModel) -> ScorerBranchModel:
    """A scorer none of the inventory's cases has an expectation for."""

    _ = commit(
        trail=ScorerTrailSchema(command="scorer-c command"),
        branch_details=BranchSchemaDetails(name="scorer-c", owner=owner.name),
    )

    return ScorerBranchModel.objects.get(owner=owner, name="scorer-c")


@pytest.mark.django_db
def test_expect_inline_renders_the_cases_expects(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    case = case_branch(owner)

    response = user_client.get(reverse("admin:orm_case_change", args=[case.pk]))

    assert response.status_code == 200
    assert f"{PREFIX}-TOTAL_FORMS".encode() in response.content
    assert b"expect payload 1 for scorer a" in response.content
    assert b"expect payload 1 for scorer b" in response.content

    assert inline_payloads(response) == [
        "expect payload 1 for scorer a",
        "expect payload 1 for scorer b",
    ]


@pytest.mark.django_db
def test_expect_inline_add_commits_a_branch_and_links_its_trail(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
    scorer_c: ScorerBranchModel,
):
    case = case_branch(owner)

    expect_a, expect_b = linked_expects(case)
    scorer_a = ScorerBranchModel.objects.get(owner=owner, name="scorer-a")
    scorer_b = ScorerBranchModel.objects.get(owner=owner, name="scorer-b")

    post_data = case_post_data(
        inventory_fixture_fdo,
        "case-1",
        expect_row("expect payload 1 for scorer a", scorer_a, expect_a),
        expect_row("expect payload 1 for scorer b", scorer_b, expect_b),
        expect_row("expected output A", scorer_c),
        initial=2,
    )

    response = user_client.post(
        reverse("admin:orm_case_change", args=[case.pk]),
        data=post_data,
        follow=True,
    )

    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    added = ExpectBranchModel.objects.get(owner=owner, name="case-1|scorer-c")
    assert added.target.payload == "expected output A"
    assert added.target.scorer_id == scorer_c.target.pk

    assert [expect.name for expect in linked_expects(case)] == [
        "expect-1-a",
        "expect-1-b",
        "case-1|scorer-c",
    ]

    # the case itself is untouched by its expects
    assert CaseBranchModel.objects.filter(owner=owner, name="case-1").count() == 1

    messages = [str(message) for message in response.context["messages"]]
    assert any("updated expects" in message for message in messages)


@pytest.mark.django_db
def test_expect_inline_add_is_idempotent(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
    scorer_c: ScorerBranchModel,
):
    case = case_branch(owner)
    change_url = reverse("admin:orm_case_change", args=[case.pk])

    post_data = case_post_data(
        inventory_fixture_fdo,
        "case-1",
        expect_row("expected output A", scorer_c),
    )

    _ = user_client.post(change_url, data=post_data, follow=True)

    added = ExpectBranchModel.objects.get(owner=owner, name="case-1|scorer-c")

    response = user_client.post(change_url, data=post_data, follow=True)
    assert response.status_code == 200

    assert [expect.pk for expect in linked_expects(case)][-1] == added.pk
    assert (
        ExpectBranchModel.objects.filter(owner=owner, name="case-1|scorer-c").count()
        == 1
    )

    messages = [str(message) for message in response.context["messages"]]
    assert any(
        "No changes detected for the 'scorer-c' expectation" in message
        for message in messages
    )


@pytest.mark.django_db
def test_expect_inline_edit_versions_the_expect_branch(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    case = case_branch(owner)
    change_url = reverse("admin:orm_case_change", args=[case.pk])

    expect_a, expect_b = linked_expects(case)
    scorer_a = ScorerBranchModel.objects.get(owner=owner, name="scorer-a")
    scorer_b = ScorerBranchModel.objects.get(owner=owner, name="scorer-b")
    first_trail = expect_a.target

    post_data = case_post_data(
        inventory_fixture_fdo,
        "case-1",
        expect_row("expect payload 1 edited", scorer_a, expect_a),
        expect_row("expect payload 1 for scorer b", scorer_b, expect_b),
        {"payload": "", "scorer": ""},
        initial=2,
    )

    response = user_client.post(change_url, data=post_data, follow=True)

    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    versions = ExpectBranchModel.objects.filter(
        owner=owner, name="expect-1-a"
    ).order_by("timestamp")
    assert len(versions) == 2
    assert versions[0].target.payload == "expect payload 1 for scorer a"
    assert versions[1].target.payload == "expect payload 1 edited"

    # the case points at the new version only
    assert [expect.pk for expect in linked_expects(case)] == [
        expect_b.pk,
        versions[1].pk,
    ]
    assert first_trail not in case.expects.all()

    response = user_client.get(change_url)
    assert inline_payloads(response) == [
        "expect payload 1 edited",
        "expect payload 1 for scorer b",
    ]


@pytest.mark.django_db
def test_expect_inline_delete_unlinks_but_keeps_the_branch(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    case = case_branch(owner)
    change_url = reverse("admin:orm_case_change", args=[case.pk])

    expect_a, expect_b = linked_expects(case)
    scorer_a = ScorerBranchModel.objects.get(owner=owner, name="scorer-a")
    scorer_b = ScorerBranchModel.objects.get(owner=owner, name="scorer-b")

    post_data = case_post_data(
        inventory_fixture_fdo,
        "case-1",
        expect_row(
            "expect payload 1 for scorer a",
            scorer_a,
            expect_a,
            delete=True,
        ),
        expect_row("expect payload 1 for scorer b", scorer_b, expect_b),
        initial=2,
    )

    response = user_client.post(change_url, data=post_data, follow=True)
    assert response.status_code == 200

    assert [expect.name for expect in linked_expects(case)] == ["expect-1-b"]
    assert ExpectBranchModel.objects.filter(owner=owner, name="expect-1-a").exists()

    response = user_client.get(change_url)
    assert inline_payloads(response) == ["expect payload 1 for scorer b"]


@pytest.mark.django_db
def test_expects_follow_the_case_to_its_new_version(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    case = case_branch(owner)
    change_url = reverse("admin:orm_case_change", args=[case.pk])

    expect_a, expect_b = linked_expects(case)
    scorer_a = ScorerBranchModel.objects.get(owner=owner, name="scorer-a")
    scorer_b = ScorerBranchModel.objects.get(owner=owner, name="scorer-b")

    post_data = case_post_data(
        inventory_fixture_fdo,
        "case-1",
        expect_row("expect payload 1 for scorer a", scorer_a, expect_a),
        expect_row("expect payload 1 for scorer b", scorer_b, expect_b),
        initial=2,
    )
    post_data["payload"] = "case payload 1, rewritten"

    response = user_client.post(change_url, data=post_data, follow=True)
    assert response.status_code == 200

    new_case = case_branch(owner)
    assert new_case.pk != case.pk
    assert new_case.target.payload == "case payload 1, rewritten"

    assert [expect.name for expect in linked_expects(new_case)] == [
        "expect-1-a",
        "expect-1-b",
    ]

    # the version the expects were edited on keeps them too
    assert [expect.name for expect in linked_expects(case)] == [
        "expect-1-a",
        "expect-1-b",
    ]

    response = user_client.get(
        reverse("admin:orm_case_change", args=[new_case.pk]),
    )
    assert inline_payloads(response) == [
        "expect payload 1 for scorer a",
        "expect payload 1 for scorer b",
    ]


@pytest.mark.django_db
def test_expect_inline_without_a_scorer_is_an_error(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    case = case_branch(owner)

    post_data = case_post_data(
        inventory_fixture_fdo,
        "case-1",
        {"payload": "expected output without a scorer"},
    )

    response = user_client.post(
        reverse("admin:orm_case_change", args=[case.pk]),
        data=post_data,
    )

    assert response.status_code == 200

    (inline,) = response.context["inline_admin_formsets"]
    assert "scorer" in inline.formset.forms[0].errors

    assert [expect.name for expect in linked_expects(case)] == [
        "expect-1-a",
        "expect-1-b",
    ]


@pytest.mark.django_db
def test_expect_inline_on_the_add_form(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
    scorer_c: ScorerBranchModel,
):
    add_url = reverse("admin:orm_case_add")

    response = user_client.get(add_url)
    assert response.status_code == 200

    (inline,) = response.context["inline_admin_formsets"]
    scorer_field = inline.formset.forms[0].fields["scorer"]
    assert list(scorer_field.queryset) == list(
        ScorerBranchModel.objects.filter(owner=owner).order_by("-timestamp")
    )

    post_data = case_post_data(
        inventory_fixture_fdo,
        "case-1",
        expect_row("expected output for a new case", scorer_c),
    )
    post_data["name"] = "case-3"
    post_data["payload"] = "case payload 3"

    response = user_client.post(add_url, data=post_data, follow=True)
    assert response.status_code == 200
    if "adminform" in response.context:
        assert response.context["adminform"].form.errors == ""

    case = case_branch(owner, "case-3")
    assert case.target.payload == "case payload 3"

    (expect,) = linked_expects(case)
    assert expect.name == "case-3|scorer-c"
    assert expect.target.payload == "expected output for a new case"

    assert CaseTrailModel.objects.filter(payload="case payload 3").count() == 1


@pytest.mark.django_db
def test_an_older_case_version_keeps_the_expects_it_was_saved_with(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    first = case_branch(owner)

    expect_a, expect_b = linked_expects(first)
    scorer_a = ScorerBranchModel.objects.get(owner=owner, name="scorer-a")
    scorer_b = ScorerBranchModel.objects.get(owner=owner, name="scorer-b")

    rows = (
        expect_row("expect payload 1 for scorer a", scorer_a, expect_a),
        expect_row("expect payload 1 for scorer b", scorer_b, expect_b),
    )

    post_data = case_post_data(inventory_fixture_fdo, "case-1", *rows, initial=2)
    post_data["payload"] = "case payload 1, rewritten"

    response = user_client.post(
        reverse("admin:orm_case_change", args=[first.pk]),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200

    second = case_branch(owner)
    assert second.pk != first.pk

    post_data = case_post_data(
        inventory_fixture_fdo,
        "case-1",
        expect_row("expect payload 1 edited", scorer_a, expect_a),
        rows[1],
        initial=2,
    )
    post_data["payload"] = "case payload 1, rewritten"

    response = user_client.post(
        reverse("admin:orm_case_change", args=[second.pk]),
        data=post_data,
        follow=True,
    )
    assert response.status_code == 200

    assert sorted(expect.target.payload for expect in linked_expects(second)) == [
        "expect payload 1 edited",
        "expect payload 1 for scorer b",
    ]

    # editing an expectation on the newer version leaves the older one alone
    assert sorted(expect.target.payload for expect in linked_expects(first)) == [
        "expect payload 1 for scorer a",
        "expect payload 1 for scorer b",
    ]


@pytest.mark.django_db
def test_a_collaborators_edit_leaves_the_owners_expects_alone(
    user_client: Client,
    inventory_fixture_fdo: InventoryFormDataOut,
    owner: IdentityModel,
):
    other = ensure_identity("olof")
    scorer = ScorerTrailSchema(command="scorer-a command")

    for trail, name in (
        (scorer, "scorer-a"),
        (ExpectTrailSchema(payload="their expectation", scorer=scorer), "shared|a"),
    ):
        _ = commit(
            trail=trail,
            branch_details=BranchSchemaDetails(name=name, owner=other.name),
        )

    _ = commit(
        trail=CaseTrailSchema(payload="shared payload"),
        branch_details=BranchSchemaDetails(
            name="shared-case",
            owner=other.name,
            collaborators=[owner.name],
            expects=["shared|a"],
        ),
    )

    theirs = CaseBranchModel.objects.get(owner=other, name="shared-case")
    change_url = reverse("admin:orm_sharedcase_change", args=[theirs.pk])

    response = user_client.get(change_url)
    assert response.status_code == 200
    assert inline_payloads(response) == ["their expectation"]

    their_expect = ExpectBranchModel.objects.get(owner=other, name="shared|a")
    their_scorer = ScorerBranchModel.objects.get(owner=other, name="scorer-a")

    post_data = case_post_data(
        inventory_fixture_fdo,
        "case-1",
        expect_row("my expectation", their_scorer, their_expect),
        initial=1,
    )
    post_data["name"] = "shared-case"
    post_data["payload"] = "shared payload"

    response = user_client.post(change_url, data=post_data, follow=True)
    assert response.status_code == 200

    mine = CaseBranchModel.objects.get(owner=owner, name="shared-case")

    # both own a branch of the same case, each with their own expectations
    assert mine.target.pk == theirs.target.pk
    assert [expect.target.payload for expect in linked_expects(mine)] == [
        "my expectation"
    ]
    assert [expect.target.payload for expect in linked_expects(theirs)] == [
        "their expectation"
    ]
