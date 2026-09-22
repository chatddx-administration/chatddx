# pyright: basic
import json

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.django.portal.forms.experiment import (
    MISMATCHED_EXPECT,
    NO_CASE_LABEL,
    NO_RUN,
    UNREADABLE_EXPECT,
)
from chatddx.django.tests.conftest import ranked_expect
from chatddx.history.models import ExperimentModel, RunModel
from chatddx.repo.entities.agent.django import AgentBranchModel
from chatddx.repo.inventories import InventoryBranchModel

pytestmark = [
    pytest.mark.django_db(transaction=True),
]


@pytest.fixture
def add_post_data(inventory_fixture_bm: InventoryBranchModel):
    case = inventory_fixture_bm["case"]["case-1"]
    expect = case.expects.first()
    assert expect is not None

    # An experiment pairs trails, not branches (see `ExperimentModel`), so
    # every one of these is the branch's target rather than the branch.
    return {
        "agent": inventory_fixture_bm["agent"]["agent-2"].target.pk,
        "case": case.target.pk,
        "expect": expect.target.pk,
        "collaborators": [],
        "initial_run_status": RunStatusChoices.QUEUED.value,
    }


def test_changelist_lists_owned_experiments(
    experiment: ExperimentModel,
    user_client: Client,
):
    response = user_client.get(reverse("admin:orm_experiment_changelist"))

    assert response.status_code == 200
    change_url = reverse("admin:orm_experiment_change", args=[experiment.pk])
    assert change_url.encode() in response.content


def test_experiment_change_form_is_read_only(
    experiment: ExperimentModel,
    user_client: Client,
):
    change_response = user_client.get(
        reverse("admin:orm_experiment_change", args=[experiment.pk])
    )
    assert change_response.status_code == 200
    assert b"View Experiment" in change_response.content
    assert b'name="_save"' not in change_response.content

    delete_response = user_client.get(
        reverse("admin:orm_experiment_delete", args=[experiment.pk])
    )
    assert delete_response.status_code == 403


def test_experiment_change_form_offers_queue_button(
    experiment: ExperimentModel,
    user_client: Client,
):
    response = user_client.get(
        reverse("admin:orm_experiment_change", args=[experiment.pk])
    )

    assert response.status_code == 200
    queue_url = reverse("admin:orm_experiment_queue", args=[experiment.pk])
    assert queue_url.encode() in response.content


def test_experiment_can_be_added_and_owner_is_assigned(
    owner: IdentityModel,
    add_post_data: dict,
    user_client: Client,
):
    add_response = user_client.get(reverse("admin:orm_experiment_add"))
    assert add_response.status_code == 200
    assert b'name="_save"' in add_response.content
    assert b"initial_run_status" in add_response.content

    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)
    assert response.status_code == 302

    created = ExperimentModel.objects.get()
    assert created.owner_id == owner.pk


def test_added_experiment_gets_a_queued_run_by_default(
    owner: IdentityModel,
    add_post_data: dict,
    user_client: Client,
):
    del add_post_data["initial_run_status"]
    form = user_client.get(reverse("admin:orm_experiment_add")).context["adminform"]
    assert (
        form.form.fields["initial_run_status"].initial == RunStatusChoices.QUEUED.value
    )

    add_post_data["initial_run_status"] = RunStatusChoices.QUEUED.value
    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)
    assert response.status_code == 302

    run = RunModel.objects.get()
    assert run.experiment_id == ExperimentModel.objects.get().pk
    assert run.status == RunStatusChoices.QUEUED
    assert run.owner_id == owner.pk


def test_added_experiment_can_get_a_stored_run(
    add_post_data: dict,
    user_client: Client,
):
    add_post_data["initial_run_status"] = RunStatusChoices.STORED.value

    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)
    assert response.status_code == 302

    assert RunModel.objects.get().status == RunStatusChoices.STORED


def test_added_experiment_gets_no_run_when_told_not_to(
    add_post_data: dict,
    user_client: Client,
):
    add_post_data["initial_run_status"] = NO_RUN

    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)
    assert response.status_code == 302

    assert ExperimentModel.objects.count() == 1
    assert not RunModel.objects.exists()


def test_added_experiment_rejects_a_status_no_run_can_start_in(
    add_post_data: dict,
    user_client: Client,
):
    add_post_data["initial_run_status"] = RunStatusChoices.COMPLETED.value

    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)

    assert response.status_code == 200
    assert not ExperimentModel.objects.exists()
    assert not RunModel.objects.exists()


def test_queue_button_creates_a_run_per_click(
    experiment: ExperimentModel,
    owner: IdentityModel,
    user_client: Client,
):
    queue_url = reverse("admin:orm_experiment_queue", args=[experiment.pk])

    first = user_client.get(queue_url)
    assert first.status_code == 302
    assert first["Location"] == reverse(
        "admin:orm_experiment_change", args=[experiment.pk]
    )

    second = user_client.get(queue_url)
    assert second.status_code == 302

    runs = RunModel.objects.filter(experiment=experiment)
    assert runs.count() == 2
    assert {run.status for run in runs} == {RunStatusChoices.QUEUED}
    assert {run.owner_id for run in runs} == {owner.pk}


@pytest.fixture
def other_owner() -> IdentityModel:
    return IdentityModel.objects.create(name="other-owner")


def test_shared_experiment_visible_only_via_shared_tab(
    shared_experiment: ExperimentModel,
    user_client: Client,
):
    change_url = reverse(
        "admin:orm_sharedexperiment_change", args=[shared_experiment.pk]
    )

    mine_response = user_client.get(reverse("admin:orm_experiment_changelist"))
    assert mine_response.status_code == 200
    assert (
        reverse("admin:orm_experiment_change", args=[shared_experiment.pk]).encode()
        not in mine_response.content
    )

    shared_response = user_client.get(reverse("admin:orm_sharedexperiment_changelist"))
    assert shared_response.status_code == 200
    assert change_url.encode() in shared_response.content


def test_shared_experiment_admin_is_read_only(
    shared_experiment: ExperimentModel,
    user_client: Client,
):
    add_response = user_client.get(reverse("admin:orm_sharedexperiment_add"))
    assert add_response.status_code == 403

    delete_response = user_client.get(
        reverse("admin:orm_sharedexperiment_delete", args=[shared_experiment.pk])
    )
    assert delete_response.status_code == 403


def test_changelist_shows_branch_names_and_links_for_agent_and_case(
    experiment: ExperimentModel,
    user_client: Client,
):
    response = user_client.get(reverse("admin:orm_experiment_changelist"))
    content = response.content.decode()

    agent_branch = experiment.agent.branches.get(owner__name=experiment.owner.name)  # pyright: ignore[reportAttributeAccessIssue]
    case_branch = experiment.case.branches.get(owner__name=experiment.owner.name)  # pyright: ignore[reportAttributeAccessIssue]

    assert f">agent-2 ({experiment.agent.fingerprint[:6]})<" in content
    assert reverse("admin:orm_superagent_change", args=[agent_branch.pk]) in content

    assert f">case-1 ({experiment.case.fingerprint[:6]})<" in content
    assert reverse("admin:orm_case_change", args=[case_branch.pk]) in content

    expect_branch = experiment.expect.branches.get(owner__name=experiment.owner.name)  # pyright: ignore[reportAttributeAccessIssue]
    assert (
        f"{expect_branch.name} ({experiment.expect.fingerprint[:6]})"
        in content.split("field-expect_")[1][:300]
    )


@pytest.mark.django_db
def test_change_view_shows_branch_names_and_links_for_agent_and_case(
    experiment: ExperimentModel,
    user_client: Client,
):
    response = user_client.get(
        reverse("admin:orm_experiment_change", args=[experiment.pk])
    )
    content = response.content.decode()

    agent_branch = experiment.agent.branches.get(owner__name=experiment.owner.name)  # pyright: ignore[reportAttributeAccessIssue]
    case_branch = experiment.case.branches.get(owner__name=experiment.owner.name)  # pyright: ignore[reportAttributeAccessIssue]

    assert reverse("admin:orm_superagent_change", args=[agent_branch.pk]) in content
    assert reverse("admin:orm_case_change", args=[case_branch.pk]) in content


def expect_widget(response):
    """The select the `expect` field renders as, past the admin's wrapper."""
    widget = response.context["adminform"].form.fields["expect"].widget

    return getattr(widget, "widget", widget)


def test_add_form_disables_expect_until_a_case_is_chosen(
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    response = user_client.get(reverse("admin:orm_experiment_add"))

    assert response.status_code == 200
    assert expect_widget(response).attrs["disabled"] is True
    assert b"data-expects-by-case" in response.content
    assert NO_CASE_LABEL.encode() in response.content


def test_add_form_maps_every_case_to_its_own_expects(
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    response = user_client.get(reverse("admin:orm_experiment_add"))
    by_case = json.loads(expect_widget(response).attrs["data-expects-by-case"])

    for name in ("case-1", "case-2"):
        case = inventory_fixture_bm["case"][name]
        assert sorted(by_case[str(case.target.pk)]) == sorted(
            case.expects.values_list("target_id", flat=True)
        )


def test_add_form_rejects_an_expect_of_another_case(
    add_post_data: dict,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    other_expect = inventory_fixture_bm["case"]["case-2"].expects.first()
    assert other_expect is not None
    assert other_expect.target_id != add_post_data["expect"]

    add_post_data["expect"] = other_expect.target_id

    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["expect"] == [MISMATCHED_EXPECT]
    assert not ExperimentModel.objects.exists()
    assert not RunModel.objects.exists()


def test_add_form_leaves_expect_enabled_once_a_case_is_posted(
    add_post_data: dict,
    user_client: Client,
):
    add_post_data["initial_run_status"] = RunStatusChoices.COMPLETED.value

    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)

    assert response.status_code == 200
    assert "disabled" not in expect_widget(response).attrs


def test_an_expectation_whose_scorer_cannot_judge_the_agent_is_refused(
    add_post_data: dict,
    inventory_fixture_bm: InventoryBranchModel,
    owner: IdentityModel,
    user_client: Client,
):
    expect = ranked_expect("case-1", owner)
    inventory_fixture_bm["case"]["case-1"].expects.add(expect)

    # agent-2 answers with an object, and reciprocal_rank reads a list
    add_post_data["expect"] = expect.target_id

    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["expect"] == [UNREADABLE_EXPECT]
    assert not ExperimentModel.objects.exists()


def test_an_expectation_whose_scorer_can_judge_the_agent_is_taken(
    add_post_data: dict,
    inventory_fixture_bm: InventoryBranchModel,
    lister: AgentBranchModel,
    owner: IdentityModel,
    user_client: Client,
):
    expect = ranked_expect("case-1", owner)
    inventory_fixture_bm["case"]["case-1"].expects.add(expect)

    add_post_data |= {"agent": lister.target.pk, "expect": expect.target_id}

    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)

    assert response.status_code == 302
    assert ExperimentModel.objects.get().expect_id == expect.target_id
