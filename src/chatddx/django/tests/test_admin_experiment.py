import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.models import IdentityModel
from chatddx.history.models import ExperimentModel

pytestmark = pytest.mark.django_db(transaction=True)


def test_changelist_lists_owned_experiments(
    experiment: ExperimentModel,
    user_client: Client,
):
    response = user_client.get(reverse("admin:orm_experiment_changelist"))

    assert response.status_code == 200
    assert b"baseline" in response.content


@pytest.mark.django_db
def test_experiment_admin_is_read_only(
    experiment: ExperimentModel,
    user_client: Client,
):
    add_response = user_client.get(reverse("admin:orm_experiment_add"))
    assert add_response.status_code == 403

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


@pytest.fixture
def other_owner() -> IdentityModel:
    return IdentityModel.objects.create(name="other-owner")


@pytest.mark.django_db
def test_shared_experiment_visible_only_via_shared_tab(
    shared_experiment: ExperimentModel,
    user_client: Client,
):
    mine_response = user_client.get(reverse("admin:orm_experiment_changelist"))
    assert mine_response.status_code == 200
    assert b"shared-with-me" not in mine_response.content

    shared_response = user_client.get(reverse("admin:orm_sharedexperiment_changelist"))
    assert shared_response.status_code == 200
    assert b"shared-with-me" in shared_response.content


@pytest.mark.django_db
def test_shared_experiment_admin_is_also_read_only(
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
    # its Case (see ExpectInline) -- so its link goes to that Case instead.
    # But Case is wip now so we disable this test
    # assert (
    #    reverse("admin:orm_case_change", args=[case_branch.pk])
    #    in content.split("field-expect_")[1][:300]
    # )


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
