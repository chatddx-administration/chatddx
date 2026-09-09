import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.experiment.models import ExperimentModel, RunModel
from chatddx.repo.base import BranchModel
from chatddx.repo.branch_models import BranchModelRegistry
from chatddx.repo.shufflers.expect import dump_expect
from chatddx.repo.shufflers.experiment import create_experiment


def _by_name(branches: dict[int, BranchModel], name: str) -> BranchModel:
    return next(branch for branch in branches.values() if branch.name == name)


@pytest.fixture
def experiment(owner: IdentityModel, branch_registry: BranchModelRegistry):
    case = _by_name(branch_registry["case"], "case-1").target
    agent = _by_name(branch_registry["agent"], "agent-2").target

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
        tags=["baseline"],
    )


@pytest.fixture
def run(owner: IdentityModel, experiment: ExperimentModel):
    return RunModel.objects.create(owner=owner, experiment=experiment)


@pytest.mark.django_db
def test_changelist_lists_owned_runs(run: RunModel, admin_client: Client):
    response = admin_client.get(reverse("admin:orm_run_changelist"))

    assert response.status_code == 200
    change_url = reverse("admin:orm_run_change", args=[run.pk])
    assert change_url.encode() in response.content


@pytest.mark.django_db
def test_run_can_be_added_and_owner_is_assigned(
    experiment: ExperimentModel,
    owner: IdentityModel,
    admin_client: Client,
):
    add_response = admin_client.get(reverse("admin:orm_run_add"))
    assert add_response.status_code == 200

    response = admin_client.post(
        reverse("admin:orm_run_add"),
        data={
            "experiment": experiment.pk,
            "status": RunStatusChoices.STORED,
            "collaborators": [],
        },
    )
    assert response.status_code == 302

    created = RunModel.objects.get(experiment=experiment)
    assert created.owner_id == owner.pk


@pytest.mark.django_db
def test_run_status_can_be_changed(run: RunModel, admin_client: Client):
    change_response = admin_client.get(reverse("admin:orm_run_change", args=[run.pk]))
    assert change_response.status_code == 200
    assert b'name="_save"' in change_response.content

    response = admin_client.post(
        reverse("admin:orm_run_change", args=[run.pk]),
        data={
            "experiment": run.experiment_id,
            "status": RunStatusChoices.QUEUED,
            "collaborators": [],
        },
    )
    assert response.status_code == 302

    run.refresh_from_db()
    assert run.status == RunStatusChoices.QUEUED


@pytest.mark.django_db
def test_requeue_action_sets_status_to_queued(run: RunModel, admin_client: Client):
    run.status = RunStatusChoices.ERRORED
    run.save(update_fields=["status"])

    response = admin_client.post(
        reverse("admin:orm_run_changelist"),
        data={
            "action": "requeue",
            "_selected_action": [str(run.pk)],
        },
    )
    assert response.status_code == 302

    run.refresh_from_db()
    assert run.status == RunStatusChoices.QUEUED


@pytest.fixture
def other_owner() -> IdentityModel:
    return IdentityModel.objects.create(name="other-owner")


@pytest.fixture
def shared_run(
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
        tags=["shared"],
    )

    run = RunModel.objects.create(owner=other_owner, experiment=experiment)
    run.collaborators.add(owner)
    return run


@pytest.mark.django_db
def test_shared_run_visible_only_via_shared_tab(
    shared_run: RunModel,
    admin_client: Client,
):
    mine_response = admin_client.get(reverse("admin:orm_run_changelist"))
    assert mine_response.status_code == 200

    change_url = reverse("admin:orm_sharedrun_change", args=[shared_run.pk])
    assert change_url.encode() not in mine_response.content

    shared_response = admin_client.get(reverse("admin:orm_sharedrun_changelist"))
    assert shared_response.status_code == 200
    assert change_url.encode() in shared_response.content
