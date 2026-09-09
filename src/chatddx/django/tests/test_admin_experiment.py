import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.models import IdentityModel
from chatddx.repo.base import BranchModel
from chatddx.repo.branch_models import BranchModelRegistry
from chatddx.repo.shufflers.expect import dump_expect
from chatddx.repo.shufflers.experiment import create_experiment


def _by_name(branches: dict[int, BranchModel], name: str) -> BranchModel:
    return next(branch for branch in branches.values() if branch.name == name)


@pytest.fixture
def experiment(owner: IdentityModel, branch_registry: BranchModelRegistry):
    case = _by_name(branch_registry["case"], "case-1").target
    agent = _by_name(
        branch_registry["agent"], "agent-2"
    ).target  # output_type-1, seed=0

    dump_expect(
        case=case,
        scorer="",
        payload="the expected answer",
        owner_name=owner.name,
    )

    return create_experiment(
        owner_name=owner.name,
        agent=agent,
        case=case,
        tags=["baseline", "smoke"],
    )


@pytest.mark.django_db
def test_changelist_lists_owned_experiments(
    experiment,
    admin_client: Client,
):
    response = admin_client.get(reverse("admin:orm_experiment_changelist"))

    assert response.status_code == 200
    assert b"baseline, smoke" in response.content


@pytest.mark.django_db
def test_experiment_admin_is_read_only(
    experiment,
    admin_client: Client,
):
    add_response = admin_client.get(reverse("admin:orm_experiment_add"))
    assert add_response.status_code == 403

    change_response = admin_client.get(
        reverse("admin:orm_experiment_change", args=[experiment.pk])
    )
    assert change_response.status_code == 200
    assert b"View Experiment" in change_response.content
    assert b'name="_save"' not in change_response.content

    delete_response = admin_client.get(
        reverse("admin:orm_experiment_delete", args=[experiment.pk])
    )
    assert delete_response.status_code == 403


@pytest.fixture
def other_owner() -> IdentityModel:
    return IdentityModel.objects.create(name="other-owner")


@pytest.fixture
def shared_experiment(
    owner: IdentityModel,
    other_owner: IdentityModel,
    branch_registry: BranchModelRegistry,
):
    case = _by_name(branch_registry["case"], "case-1").target
    agent = _by_name(branch_registry["agent"], "agent-2").target

    dump_expect(
        case=case,
        scorer="",
        payload="the expected answer",
        owner_name=other_owner.name,
    )

    experiment = create_experiment(
        owner_name=other_owner.name,
        agent=agent,
        case=case,
        tags=["shared-with-me"],
    )
    experiment.collaborators.add(owner)
    return experiment


@pytest.mark.django_db
def test_shared_experiment_visible_only_via_shared_tab(
    shared_experiment,
    admin_client: Client,
):
    mine_response = admin_client.get(reverse("admin:orm_experiment_changelist"))
    assert mine_response.status_code == 200
    assert b"shared-with-me" not in mine_response.content

    shared_response = admin_client.get(reverse("admin:orm_sharedexperiment_changelist"))
    assert shared_response.status_code == 200
    assert b"shared-with-me" in shared_response.content


@pytest.mark.django_db
def test_shared_experiment_admin_is_also_read_only(
    shared_experiment,
    admin_client: Client,
):
    add_response = admin_client.get(reverse("admin:orm_sharedexperiment_add"))
    assert add_response.status_code == 403

    delete_response = admin_client.get(
        reverse("admin:orm_sharedexperiment_delete", args=[shared_experiment.pk])
    )
    assert delete_response.status_code == 403


@pytest.mark.django_db
def test_changelist_shows_branch_names_and_links_for_agent_and_case(
    experiment,
    admin_client: Client,
):
    response = admin_client.get(reverse("admin:orm_experiment_changelist"))
    content = response.content.decode()

    agent_branch = experiment.agent.branches.get(owner__name=experiment.owner.name)
    case_branch = experiment.case.branches.get(owner__name=experiment.owner.name)

    assert f">agent-2 ({experiment.agent.fingerprint[:6]})<" in content
    assert reverse("admin:orm_superagent_change", args=[agent_branch.pk]) in content

    assert f">case-1 ({experiment.case.fingerprint[:6]})<" in content
    assert reverse("admin:orm_case_change", args=[case_branch.pk]) in content

    # Expect has no admin page of its own -- it's only ever edited inline on
    # its Case (see ExpectInline) -- so its link goes to that Case instead.
    assert (
        reverse("admin:orm_case_change", args=[case_branch.pk])
        in content.split("field-expect_")[1][:300]
    )


@pytest.mark.django_db
def test_change_view_shows_branch_names_and_links_for_agent_and_case(
    experiment,
    admin_client: Client,
):
    response = admin_client.get(
        reverse("admin:orm_experiment_change", args=[experiment.pk])
    )
    content = response.content.decode()

    agent_branch = experiment.agent.branches.get(owner__name=experiment.owner.name)
    case_branch = experiment.case.branches.get(owner__name=experiment.owner.name)

    assert reverse("admin:orm_superagent_change", args=[agent_branch.pk]) in content
    assert reverse("admin:orm_case_change", args=[case_branch.pk]) in content
