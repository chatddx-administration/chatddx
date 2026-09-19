import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.django.portal.forms.experiment import NO_RUN
from chatddx.history.models import ExperimentModel, RunModel
from chatddx.repo.inventories import InventoryBranchModel

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def add_post_data(inventory_fixture_bm: InventoryBranchModel):
    case = inventory_fixture_bm["case"]["case-1"]
    expect = case.expects.first()
    assert expect is not None

    return {
        "agent": inventory_fixture_bm["agent"]["agent-2"].target.pk,
        "case": case.target.pk,
        "expect": expect.pk,
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


@pytest.mark.django_db
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


@pytest.mark.django_db
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


@pytest.mark.django_db
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


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_added_experiment_can_get_a_stored_run(
    add_post_data: dict,
    user_client: Client,
):
    add_post_data["initial_run_status"] = RunStatusChoices.STORED.value

    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)
    assert response.status_code == 302

    assert RunModel.objects.get().status == RunStatusChoices.STORED


@pytest.mark.django_db
def test_added_experiment_gets_no_run_when_told_not_to(
    add_post_data: dict,
    user_client: Client,
):
    add_post_data["initial_run_status"] = NO_RUN

    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)
    assert response.status_code == 302

    assert ExperimentModel.objects.count() == 1
    assert not RunModel.objects.exists()


@pytest.mark.django_db
def test_added_experiment_rejects_a_status_no_run_can_start_in(
    add_post_data: dict,
    user_client: Client,
):
    add_post_data["initial_run_status"] = RunStatusChoices.COMPLETED.value

    response = user_client.post(reverse("admin:orm_experiment_add"), add_post_data)

    assert response.status_code == 200
    assert not ExperimentModel.objects.exists()
    assert not RunModel.objects.exists()


@pytest.mark.django_db
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


@pytest.mark.django_db
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


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_changelist_shows_branch_names_and_links_for_agent_and_case(
    experiment: ExperimentModel,
    user_client: Client,
):
    response = user_client.get(reverse("admin:orm_experiment_changelist"))
    content = response.content.decode()

    agent_branch = experiment.agent.branches.get(owner__name=experiment.owner.name)
    case_branch = experiment.case.branches.get(owner__name=experiment.owner.name)

    assert f">agent-2 ({experiment.agent.fingerprint[:6]})<" in content
    assert reverse("admin:orm_superagent_change", args=[agent_branch.pk]) in content

    assert f">case-1 ({experiment.case.fingerprint[:6]})<" in content
    assert reverse("admin:orm_case_change", args=[case_branch.pk]) in content

    # Expect has no admin page of its own -- it's only ever edited inline on
    # its Case (see ExpectInline) -- so it reads as a name, not as a link.
    expect_branch = experiment.expect.branches.get(owner__name=experiment.owner.name)
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

    agent_branch = experiment.agent.branches.get(owner__name=experiment.owner.name)
    case_branch = experiment.case.branches.get(owner__name=experiment.owner.name)

    assert reverse("admin:orm_superagent_change", args=[agent_branch.pk]) in content
    assert reverse("admin:orm_case_change", args=[case_branch.pk]) in content
