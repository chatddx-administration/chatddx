# pyright: basic
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel, TagModel
from chatddx.django.portal.pages.batch import CONFIRM_FIELD
from chatddx.history.batches import EXCLUDED_SHOWN, BatchPlan, PlanRow, plan
from chatddx.history.models import BatchModel, ExperimentModel, RunModel
from chatddx.history.proxies import ALL_SCORERS
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.scorer.django import Scorer
from chatddx.repo.inventories import InventoryBranchModel

pytestmark = [
    pytest.mark.django_db(transaction=True),
]

ADD_URL = reverse("admin:orm_batch_add")


class Lab:
    def __init__(self, inventory: InventoryBranchModel, owner: IdentityModel):
        self.owner = owner
        self.agent = inventory["agent"]["agent-2"].target
        self.cases = inventory["case"]
        self.tags = {
            tag.name: tag for tag in TagModel.objects.filter(owner=owner, entity="case")
        }
        self.scorers = {
            scorer.name: scorer for scorer in Scorer.objects.filter(owner=owner)
        }

    def tag(self, case_name: str, tag_name: str) -> CaseBranchModel:
        case = self.cases[case_name]
        case.tags.add(self.tags[tag_name])

        return case

    def drop_expect(self, case_name: str, scorer_name: str) -> None:
        case = self.cases[case_name]
        scorer = self.scorers[scorer_name]

        for expect in case.expects.all():
            if expect.target.scorer_id == scorer.target_id:
                case.expects.remove(expect)

    def post_data(self, **overrides: Any) -> dict[str, Any]:
        return {
            "agent": self.agent.pk,
            "case_tags": [self.tags["tag-1"].pk],
            "scorers": [],
            "queue_immediately": "on",
        } | overrides


@pytest.fixture
def lab(inventory_fixture_bm: InventoryBranchModel, owner: IdentityModel) -> Lab:
    return Lab(inventory_fixture_bm, owner)


def confirmed(data: dict[str, Any]) -> dict[str, Any]:
    return data | {CONFIRM_FIELD: "yes"}


def messages_of(response: Any) -> list[str]:
    return [str(message) for message in response.context["messages"]]


def test_the_add_form_offers_the_batch_fields_and_queues_by_default(
    lab: Lab,
    user_client: Client,
):
    response = user_client.get(ADD_URL)

    assert response.status_code == 200

    form = response.context["adminform"].form

    assert list(form.fields) == ["agent", "case_tags", "scorers", "queue_immediately"]
    assert form.fields["queue_immediately"].initial is True
    assert form.fields["scorers"].required is False

    # every scorer of the owner's is on offer, the way a plain m2m lists them
    assert sorted(scorer.name for scorer in form.fields["scorers"].queryset) == [
        "scorer-a",
        "scorer-b",
        "some-scorer",
    ]
    assert sorted(tag.name for tag in form.fields["case_tags"].queryset) == [
        "tag-1",
        "tag-2",
    ]


def test_uuid_and_timestamp_have_no_input_field(lab: Lab, user_client: Client):
    response = user_client.get(ADD_URL)

    assert b'name="uuid"' not in response.content
    assert b'name="timestamp"' not in response.content


def test_saving_confirms_before_anything_is_written(lab: Lab, user_client: Client):
    response = user_client.post(ADD_URL, lab.post_data())

    assert response.status_code == 200
    assert not BatchModel.objects.exists()
    assert not ExperimentModel.objects.exists()

    # case-1 carries tag-1 and expects both scorers
    assert response.context["plan"].total == 2
    assert response.context["confirm_field"] == CONFIRM_FIELD
    assert CONFIRM_FIELD.encode() in response.content


def test_the_confirmation_counts_the_experiments_per_tag_and_scorer(
    lab: Lab,
    user_client: Client,
):
    lab.tag("case-2", "tag-1")

    response = user_client.post(
        ADD_URL,
        lab.post_data(
            case_tags=[lab.tags["tag-1"].pk, lab.tags["tag-2"].pk],
            scorers=[lab.scorers["scorer-a"].pk, lab.scorers["scorer-b"].pk],
        ),
    )

    assert response.status_code == 200

    batch_plan = response.context["plan"]

    assert batch_plan.rows == (
        PlanRow(tag="tag-1", scorer="scorer-a", count=2),
        PlanRow(tag="tag-1", scorer="scorer-b", count=2),
        PlanRow(tag="tag-2", scorer="scorer-a", count=1),
        PlanRow(tag="tag-2", scorer="scorer-b", count=1),
    )
    # case-1 carries both tags, so it is counted under both and run once
    assert batch_plan.total == 4
    assert batch_plan.overlapping is True


def test_confirming_generates_experiments_with_queued_runs(
    lab: Lab,
    owner: IdentityModel,
    user_client: Client,
):
    response = user_client.post(ADD_URL, confirmed(lab.post_data()))

    assert response.status_code == 302

    batch = BatchModel.objects.get()

    assert batch.owner_id == owner.pk
    assert batch.agent_id == lab.agent.pk
    assert list(batch.case_tags.all()) == [lab.tags["tag-1"]]
    assert not batch.scorers.exists()

    experiments = ExperimentModel.objects.all()

    assert experiments.count() == 2
    assert all(experiment.batch_id == batch.pk for experiment in experiments)
    assert all(experiment.agent_id == lab.agent.pk for experiment in experiments)

    runs = RunModel.objects.all()

    assert runs.count() == 2
    assert {run.status for run in runs} == {RunStatusChoices.QUEUED}
    assert {run.experiment_id for run in runs} == {
        experiment.pk for experiment in experiments
    }


def test_an_unqueued_batch_stores_its_runs(lab: Lab, user_client: Client):
    data = lab.post_data()
    del data["queue_immediately"]

    response = user_client.post(ADD_URL, confirmed(data))

    assert response.status_code == 302
    assert {run.status for run in RunModel.objects.all()} == {RunStatusChoices.STORED}


def test_naming_scorers_narrows_what_is_generated(lab: Lab, user_client: Client):
    response = user_client.post(
        ADD_URL,
        confirmed(lab.post_data(scorers=[lab.scorers["scorer-a"].pk])),
    )

    assert response.status_code == 302

    experiment = ExperimentModel.objects.get()

    assert experiment.expect.scorer_id == lab.scorers["scorer-a"].target_id  # pyright: ignore[reportAttributeAccessIssue]


def test_cases_without_the_chosen_scorer_are_named_before_generating(
    lab: Lab,
    user_client: Client,
):
    lab.tag("case-2", "tag-1")
    lab.drop_expect("case-2", "scorer-b")

    response = user_client.post(
        ADD_URL,
        lab.post_data(scorers=[lab.scorers["scorer-b"].pk]),
    )

    assert response.status_code == 200

    batch_plan = response.context["plan"]

    assert batch_plan.excluded == ("case-2",)
    assert batch_plan.total == 1
    assert b"case-2" in response.content

    # and nothing is written until the user says so
    assert not ExperimentModel.objects.exists()

    response = user_client.post(
        ADD_URL,
        confirmed(lab.post_data(scorers=[lab.scorers["scorer-b"].pk])),
        follow=True,
    )

    assert ExperimentModel.objects.count() == 1
    assert any("case-2" in message for message in messages_of(response))


def test_nothing_to_generate_leaves_the_confirmation_without_a_button(
    lab: Lab,
    user_client: Client,
):
    lab.drop_expect("case-1", "scorer-a")
    lab.drop_expect("case-1", "scorer-b")

    response = user_client.post(ADD_URL, lab.post_data())

    assert response.status_code == 200
    assert response.context["plan"].total == 0
    assert f'name="{CONFIRM_FIELD}"'.encode() not in response.content


def test_an_invalid_post_comes_back_as_the_add_form(lab: Lab, user_client: Client):
    response = user_client.post(ADD_URL, lab.post_data(case_tags=[]))

    assert response.status_code == 200
    assert response.context["adminform"].form.errors
    assert not BatchModel.objects.exists()


def test_the_changelist_shows_what_a_batch_stands_for(
    lab: Lab,
    user_client: Client,
):
    user_client.post(ADD_URL, confirmed(lab.post_data()))
    batch = BatchModel.objects.get()

    response = user_client.get(reverse("admin:orm_batch_changelist"))

    assert response.status_code == 200
    assert reverse("admin:orm_batch_change", args=[batch.pk]).encode() in (
        response.content
    )
    assert b"tag-1" in response.content
    # a batch that named no scorer runs every scorer its cases carry
    assert ALL_SCORERS.encode() in response.content


def test_the_change_form_is_read_only_and_offers_re_queue(
    lab: Lab,
    user_client: Client,
):
    user_client.post(
        ADD_URL,
        confirmed(lab.post_data(scorers=[lab.scorers["scorer-a"].pk])),
    )
    batch = BatchModel.objects.get()

    response = user_client.get(reverse("admin:orm_batch_change", args=[batch.pk]))

    assert response.status_code == 200
    assert b'name="_save"' not in response.content
    assert str(batch.uuid).encode() in response.content
    # every field is shown, and each reads as what it stands for
    assert b"tag-1" in response.content
    assert b"scorer-a" in response.content
    assert reverse("admin:orm_batch_requeue", args=[batch.pk]).encode() in (
        response.content
    )

    delete_response = user_client.get(
        reverse("admin:orm_batch_delete", args=[batch.pk])
    )

    assert delete_response.status_code == 403


def test_re_queue_confirms_and_then_generates_another_queued_set(
    lab: Lab,
    user_client: Client,
):
    data = lab.post_data()
    del data["queue_immediately"]
    user_client.post(ADD_URL, confirmed(data))

    batch = BatchModel.objects.get()
    requeue_url = reverse("admin:orm_batch_requeue", args=[batch.pk])

    confirmation = user_client.get(requeue_url)

    assert confirmation.status_code == 200
    assert confirmation.context["plan"].total == 2
    assert ExperimentModel.objects.count() == 2

    response = user_client.post(requeue_url, {CONFIRM_FIELD: "yes"})

    assert response.status_code == 302
    assert ExperimentModel.objects.count() == 4
    assert ExperimentModel.objects.filter(batch=batch).count() == 4

    statuses = [run.status for run in RunModel.objects.all()]

    assert sorted(statuses) == sorted(
        [RunStatusChoices.STORED] * 2 + [RunStatusChoices.QUEUED] * 2
    )


def test_another_owners_batch_is_out_of_reach(
    lab: Lab,
    other_owner: IdentityModel,
    user_client: Client,
):
    batch = BatchModel.objects.create(owner=other_owner, agent=lab.agent)

    response = user_client.get(reverse("admin:orm_batch_requeue", args=[batch.pk]))

    assert response.status_code == 404
    assert not ExperimentModel.objects.exists()


def test_the_experiment_traces_back_to_its_batch(lab: Lab, user_client: Client):
    user_client.post(ADD_URL, confirmed(lab.post_data()))

    batch = BatchModel.objects.get()
    experiment = ExperimentModel.objects.first()

    assert experiment is not None

    response = user_client.get(
        reverse("admin:orm_experiment_change", args=[experiment.pk])
    )

    assert response.status_code == 200
    assert reverse("admin:orm_batch_change", args=[batch.pk]).encode() in (
        response.content
    )


def test_an_untagged_case_is_left_alone(lab: Lab, user_client: Client):
    batch_plan = plan("alex", [lab.tags["tag-1"]], [])

    # case-2 carries no tag, so it is not in the batch at all -- not excluded
    assert batch_plan.excluded == ()
    assert batch_plan.total == 2


def test_the_excluded_cases_are_counted_and_truncated():
    names = tuple(f"case-{index}" for index in range(EXCLUDED_SHOWN + 3))
    batch_plan = BatchPlan(rows=(), pairs=(), excluded=names)

    assert batch_plan.excluded_shown == names[:EXCLUDED_SHOWN]
    assert batch_plan.excluded_rest == 3
