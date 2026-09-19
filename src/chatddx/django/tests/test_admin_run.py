# pyright: basic
import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.choices import RunStatusChoices, SessionContextChoices
from chatddx.core.models import IdentityModel
from chatddx.history.models import ExperimentModel, RunModel, SessionModel
from chatddx.repo.inventories import InventoryBranchModel


@pytest.mark.django_db
def test_changelist_lists_owned_runs(run: RunModel, user_client: Client):
    response = user_client.get(reverse("admin:orm_run_changelist"))

    assert response.status_code == 200
    change_url = reverse("admin:orm_run_change", args=[run.pk])
    assert change_url.encode() in response.content


@pytest.mark.django_db
def test_run_can_be_added_and_owner_is_assigned(
    experiment: ExperimentModel,
    owner: IdentityModel,
    user_client: Client,
):
    add_response = user_client.get(reverse("admin:orm_run_add"))
    assert add_response.status_code == 200

    response = user_client.post(
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
def test_run_status_can_be_changed(run: RunModel, user_client: Client):
    change_response = user_client.get(reverse("admin:orm_run_change", args=[run.pk]))
    assert change_response.status_code == 200
    assert b'name="_save"' in change_response.content

    response = user_client.post(
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
def test_requeue_action_sets_status_to_queued(run: RunModel, user_client: Client):
    run.status = RunStatusChoices.ERRORED
    run.save(update_fields=["status"])

    response = user_client.post(
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
def shared_run(
    owner: IdentityModel,
    experiment: ExperimentModel,
    other_owner: IdentityModel,
    inventory_fixture_bm: InventoryBranchModel,
):
    run = RunModel.objects.create(owner=other_owner, experiment=experiment)
    run.collaborators.add(owner)
    return run


@pytest.mark.django_db
def test_shared_run_visible_only_via_shared_tab(
    shared_run: RunModel,
    user_client: Client,
):
    mine_response = user_client.get(reverse("admin:orm_run_changelist"))
    assert mine_response.status_code == 200

    change_url = reverse("admin:orm_sharedrun_change", args=[shared_run.pk])
    assert change_url.encode() not in mine_response.content

    shared_response = user_client.get(reverse("admin:orm_sharedrun_changelist"))
    assert shared_response.status_code == 200
    assert change_url.encode() in shared_response.content


@pytest.mark.django_db
def test_collaborators_field_excludes_owner(
    owner: IdentityModel,
    experiment: ExperimentModel,
    user_client: Client,
):
    other = IdentityModel.objects.create(name="collaborator")

    response = user_client.get(reverse("admin:orm_run_add"))
    content = response.content.decode()

    field_html = content.split('id="id_collaborators"')[1].split("</select>")[0]
    assert f'value="{other.pk}"' in field_html
    assert f'value="{owner.pk}"' not in field_html


@pytest.mark.django_db
def test_experiment_dropdown_shows_timestamp_and_uuid(
    experiment: ExperimentModel,
    user_client: Client,
):
    response = user_client.get(reverse("admin:orm_run_add"))
    content = response.content.decode()

    timestamp = experiment.timestamp.strftime("%Y-%m-%d %H:%M")
    assert f"{timestamp} — {str(experiment.uuid)[:8]}" in content


@pytest.mark.django_db
def test_changelist_shows_experiment_timestamp_and_uuid(
    run: RunModel,
    experiment: ExperimentModel,
    user_client: Client,
):
    response = user_client.get(reverse("admin:orm_run_changelist"))
    content = response.content.decode()

    timestamp = experiment.timestamp.strftime("%Y-%m-%d %H:%M")
    assert f"{timestamp} — {str(experiment.uuid)[:8]}" in content


@pytest.mark.django_db
def test_session_field_is_a_link_not_a_dropdown(run: RunModel, user_client: Client):
    session = SessionModel.objects.create(
        owner=run.owner,
        context=SessionContextChoices.EXPERIMENT,
    )
    run.session = session
    run.save(update_fields=["session"])

    response = user_client.get(reverse("admin:orm_run_change", args=[run.pk]))
    content = response.content.decode()

    field_html = content.split(">Session</label>")[1][:500]
    assert "<select" not in field_html
    assert reverse("admin:orm_session_change", args=[session.pk]) in field_html


@pytest.mark.django_db
def test_result_field_is_read_only_and_json_highlighted(
    run: RunModel, user_client: Client
):
    run.result = {"score": 1}
    run.save(update_fields=["result"])

    response = user_client.get(reverse("admin:orm_run_change", args=[run.pk]))
    content = response.content.decode()

    field_html = content.split(">Result</label>")[1][:500]
    assert 'name="result"' not in field_html
    assert 'class="highlight"' in field_html
    assert "score" in field_html


@pytest.mark.django_db
def test_result_field_does_not_render_as_literal_null(
    run: RunModel, user_client: Client
):
    """Run.result is a nullable JSONField; a fresh Run has result=None,
    and the read-only display shouldn't show the literal text "null"."""
    response = user_client.get(reverse("admin:orm_run_change", args=[run.pk]))
    content = response.content.decode()

    field_html = content.split(">Result</label>")[1][:500]
    assert ">null<" not in field_html
