"""ExperimentAdmin and SharedExperimentAdmin: read-only admin pages for
Experiment, akin to Session/SharedSession
(chatddx.django.portal.admin.history) -- listed, filtered to the current
owner (or, for the shared variant, to experiments shared with them as a
collaborator), but never add/change/delete-able (see
chatddx.experiment.models.ExperimentModel's docstring for why: an
Experiment is only ever generated, never hand-authored or edited).
"""

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
    output_type = _by_name(branch_registry["output_type"], "output_type-1").target
    agent = _by_name(branch_registry["agent"], "agent-2").target  # output_type-1, seed=0

    dump_expect(
        case=case,
        output_type=output_type,
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
    # Nothing can be hand-authored: the add form is unreachable.
    add_response = admin_client.get(reverse("admin:orm_experiment_add"))
    assert add_response.status_code == 403

    # The detail page stays reachable -- has_view_permission defaults to
    # True for a superuser regardless of has_change_permission -- but
    # Django renders it in its read-only "View Experiment" mode rather
    # than an editable form, since has_change_permission is False.
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
    """An Experiment owned by someone else, shared with `owner` (the
    admin_client user) as a collaborator -- the counterpart to
    SharedSession, reachable only through SharedExperimentAdmin."""
    case = _by_name(branch_registry["case"], "case-1").target
    output_type = _by_name(branch_registry["output_type"], "output_type-1").target
    agent = _by_name(branch_registry["agent"], "agent-2").target

    dump_expect(
        case=case,
        output_type=output_type,
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
    # It's not mine, so it doesn't show up on "My Experiments" ...
    mine_response = admin_client.get(reverse("admin:orm_experiment_changelist"))
    assert mine_response.status_code == 200
    assert b"shared-with-me" not in mine_response.content

    # ... only on "Shared with Me".
    shared_response = admin_client.get(
        reverse("admin:orm_sharedexperiment_changelist")
    )
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
