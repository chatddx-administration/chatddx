# pyright: basic
import re
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from chatddx.dev.fake_vllm import FakeTransport
from chatddx.django.portal.admin import CONFIRM, LATER, RUN
from chatddx.django.portal.models import BatchModel
from chatddx.history.models import RunModel, RunStatus
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.worker import control, worker
from chatddx.worker.models import JobModel, Status, Stopping, WorkerStateModel

pytestmark = pytest.mark.django_db

FAKE = "qwen3-8b-awq@fake"
ADD = reverse("admin:portal_batch_add")
CHANGELIST = reverse("admin:portal_batch_changelist")
STATUS = reverse("admin:portal_batch_status")
PANEL = reverse("admin:portal_batch_status_panel")
CONTROL = reverse("admin:portal_batch_status_control")

FREE_TEXT = {
    "configuration": "free-text",
    "stack": FAKE,
    "case_tags": ["tag-2"],
    "seed": "42",
}


def kept(client: Client, how: str = RUN, **asked: Any) -> BatchModel:
    """A batch planned, confirmed and kept, to run now or later: its page seen."""
    response = client.post(ADD, FREE_TEXT | asked | {CONFIRM: how}, follow=True)
    assert response.redirect_chain, response.content

    return BatchModel.objects.order_by("-pk").first()  # pyright: ignore[reportReturnType]


def page_of(batch: BatchModel, of: str = "change") -> str:
    return reverse(f"admin:portal_batch_{of}", args=[batch.pk])


def jobs(**filters: Any) -> list[JobModel]:
    return list(JobModel.objects.filter(**filters).order_by("pk"))


def tabs(response: Any) -> list[tuple[str, bool]]:
    """The Batches' tabs on a page: where each leads, and whether it is the one."""
    [nav] = re.findall(
        r'<nav id="tabs-items".*?</nav>', response.content.decode(), re.DOTALL
    )

    return [
        (href, "active" in classes)
        for href, classes in re.findall(r'<a href="([^"]*)" class="([^"]*)"', nav)
    ]


def said(response: Any) -> list[str]:
    return [str(message) for message in response.context["messages"]]


def at_once(max_jobs: int, stack: str = FAKE) -> None:
    for model in StackBranchModel.objects.filter(name=stack):
        model.details = {**model.details, "max_jobs": max_jobs}
        model.save()


def under_way(case: str, owner: str = "alice", tokens: int = 0) -> None:
    """The owner's `case` taken up by a worker at work: seen just now, its beat fresh."""
    now = timezone.now()
    _ = WorkerStateModel.objects.update_or_create(pk=1, defaults={"seen": now})
    _ = JobModel.objects.filter(owner__name=owner, case=case).update(
        status=Status.RUNNING, started=now, beat=now, tokens=tokens
    )


def pressed(client: Client, action: str, htmx: bool = True) -> Any:
    headers = {"HX-Request": "true"} if htmx else {}
    return client.post(CONTROL, {"action": action}, headers=headers)


def test_a_batch_run_now_puts_its_trials_in_the_worker_s_queue(alice: Client):
    batch = kept(alice, reasoning=["default", "off"])
    queued = jobs()

    assert [(job.label, job.case) for job in queued] == [
        ("free-text", "case-1"),
        ("free-text", "case-2"),
        ("free-text+reasoning=off", "case-1"),
        ("free-text+reasoning=off", "case-2"),
    ]
    assert {(job.batch, job.owner.name, job.status) for job in queued} == {
        (batch.uuid, "alice", Status.QUEUED)
    }
    assert [job.fingerprint for job in queued[::2]] == [
        cell["fingerprint"] for cell in batch.cells
    ]


def test_a_batch_run_now_leads_to_the_status_page(alice: Client):
    response = alice.post(ADD, FREE_TEXT | {CONFIRM: RUN}, follow=True)

    assert f'href="{STATUS}">Follow them on the status page.</a>'.encode() in (
        response.content
    )


def test_a_batch_kept_for_later_is_run_from_its_own_page(alice: Client):
    batch = kept(alice, LATER)

    assert {job.status for job in jobs()} == {Status.STORED}

    page = alice.get(page_of(batch))

    assert page.context["batch_shown"].said == "Kept for later: none of it has run."
    assert b'value="resume"' in page.content
    assert b"Run the batch" in page.content

    ran = alice.post(page_of(batch, "run"), {"action": "resume"}, follow=True)

    assert said(ran) == ["2 trials of the batch queued for the worker."]
    assert {job.status for job in jobs()} == {Status.QUEUED}
    assert ran.context["batch_shown"].said == "Queued: up next."


def test_the_status_page_is_one_of_the_batches(alice: Client):
    response = alice.get(STATUS)

    assert response.status_code == 200
    assert tabs(response) == [(CHANGELIST, False), (STATUS, True)]
    assert tabs(alice.get(CHANGELIST)) == [(CHANGELIST, True), (STATUS, False)]
    assert f'hx-get="{PANEL}"'.encode() in response.content
    assert b'hx-trigger="every 1s"' in response.content
    assert b"Nothing has been queued yet." in response.content


def test_the_status_counts_the_owner_s_batches_and_shows_their_cases_taken_up_last(
    alice: Client, fake: FakeTransport
):
    batch = kept(alice)
    _ = worker.run(fake)
    response = alice.get(PANEL)
    shown = response.context["shown"]

    assert shown.progress.counted == "0 running · 2 completed · 2 total"
    assert [link.pk for link in shown.batches] == [batch.pk]
    assert {(ran.case, ran.cell, ran.outcome) for ran in shown.latest} == {
        ("case-1", "free-text × qwen3-8b-awq@fake", "completed"),
        ("case-2", "free-text × qwen3-8b-awq@fake", "completed"),
    }
    # case-2's, which comes last or not as the two run side by side
    [second] = [ran for ran in shown.latest if ran.case == "case-2"]

    assert dict(second.scores) == {"first_mention": "—", "reciprocal_rank": "0"}
    assert b"Idle: nothing of yours is queued." in response.content
    assert b"reciprocal_rank 0" in response.content
    assert f'href="{page_of(batch)}"'.encode() in response.content


def test_the_status_shows_the_owner_s_own_alone(
    alice: Client, bob: Client, fake: FakeTransport
):
    _ = kept(bob)
    _ = worker.run(fake)
    _ = kept(alice)
    shown = alice.get(PANEL).context["shown"]

    assert shown.latest == []
    assert shown.progress.counted == "0 running · 0 completed · 2 total"
    assert shown.up_next is not None and shown.up_next.owner.name == "alice"

    changelist = bob.get(CHANGELIST)

    assert [batch.owner.name for batch in changelist.context["cl"].result_list] == [
        "bob"
    ]


def test_behind_another_s_jobs_the_owner_s_wait_for_their_turn(
    alice: Client, bob: Client
):
    at_once(1)
    _ = kept(bob)
    batch = kept(alice)
    under_way("case-1", owner="bob")
    response = alice.get(PANEL)
    shown = response.context["shown"]

    assert shown.said == "Waiting for our turn."
    assert [(waits.stack, waits.running, waits.queued) for waits in shown.waiting] == [
        (FAKE, 1, 1)
    ]
    assert b"On qwen3-8b-awq@fake: 2 cases ahead of ours, 1 of them running." in (
        response.content
    )
    assert alice.get(page_of(batch)).context["batch_shown"].said == (
        "Waiting for our turn on qwen3-8b-awq@fake: 2 cases ahead of ours."
    )
    # bob, whose turn it is, waits for no one
    assert bob.get(PANEL).context["shown"].said == "Running."


def test_the_owner_s_cases_running_are_shown_with_their_tallies_live(alice: Client):
    _ = kept(alice)
    under_way("case-1", tokens=12)
    response = alice.get(PANEL)
    shown = response.context["shown"]

    assert [now.job.case for now in shown.running] == ["case-1"]
    assert shown.progress.counted == "1 running · 0 completed · 2 total"
    assert b"~12 tokens" in response.content
    assert b"Running." in response.content


def test_up_next_is_the_owner_s_first_queued_with_how_many_are_outstanding(
    alice: Client,
):
    _ = kept(alice, reasoning=["default", "off"])
    under_way("case-1")
    shown = alice.get(PANEL).context["shown"]

    assert shown.up_next is not None
    assert (shown.up_next.case, shown.up_next.label) == ("case-2", "free-text")
    assert shown.outstanding == 2


def test_the_worker_not_seen_is_said(alice: Client):
    response = alice.get(PANEL)

    assert b"The worker isn&#x27;t running" in response.content


def test_pause_resumes_as_it_is_pressed_again_for_the_owner_alone(
    alice: Client, bob: Client
):
    paused = pressed(alice, "pause")

    assert paused.status_code == 200
    assert control.state("alice").paused
    assert not control.state("bob").paused
    assert b'value="resume"' in paused.content

    resumed = pressed(alice, "resume", htmx=False)

    assert resumed.status_code == 302 and resumed["Location"] == STATUS
    assert not control.state("alice").paused


def test_stop_once_waits_for_the_cases_running_and_twice_stops_them(alice: Client):
    _ = kept(alice)
    under_way("case-1")

    once = pressed(alice, "stop")

    assert control.state("alice").stopping == Stopping.AFTER
    assert [job.status for job in jobs()] == [Status.RUNNING, Status.STOPPED]
    assert b"Stop now" in once.content
    assert b"Stopping after the case running" in once.content

    twice = pressed(alice, "stop")

    assert control.state("alice").stopping == Stopping.NOW
    assert b"Stopping now." in twice.content
    assert b"disabled" in twice.content


def test_stop_with_nothing_running_takes_the_owner_s_queue_out_and_no_one_else_s(
    alice: Client, bob: Client
):
    _ = kept(alice)
    _ = kept(bob)

    response = pressed(alice, "stop")

    assert {job.status for job in jobs(owner__name="alice")} == {Status.STOPPED}
    assert {job.status for job in jobs(owner__name="bob")} == {Status.QUEUED}
    assert response.context["shown"].progress.counted == (
        "0 running · 0 completed · 2 total · 2 stopped"
    )
    assert response.context["shown"].progress.stopped_share == "100.00"


def test_the_controls_take_a_post(alice: Client):
    assert alice.get(CONTROL).status_code == 405


def test_a_batch_stopped_is_resumed_from_its_page_and_run_again_once_completed(
    alice: Client, fake: FakeTransport
):
    batch = kept(alice)
    _ = pressed(alice, "stop")
    page = alice.get(page_of(batch))

    assert page.context["batch_shown"].said == "Stopped: 0 of 2 completed."
    assert b"Resume the batch" in page.content

    _ = alice.post(page_of(batch, "run"), {"action": "resume"})
    _ = worker.run(fake)
    page = alice.get(page_of(batch))

    assert page.context["batch_shown"].said == "Completed: all 2."
    assert b"Run it again" in page.content
    assert b'value="rerun"' in page.content

    again = alice.post(page_of(batch, "run"), {"action": "rerun"}, follow=True)

    assert said(again) == ["2 trials of the batch queued for the worker."]
    assert {job.status for job in jobs()} == {Status.QUEUED}


def test_a_batch_kept_before_the_queue_was_runs_from_its_page(alice: Client):
    batch = kept(alice, LATER)
    _ = JobModel.objects.all().delete()

    _ = alice.post(page_of(batch, "run"), {"action": "resume"})

    assert [(job.case, job.status) for job in jobs()] == [
        ("case-1", Status.QUEUED),
        ("case-2", Status.QUEUED),
    ]


def test_more_cases_join_a_batch_stored_or_queued_as_the_batch_stands(
    alice: Client,
):
    batch = kept(alice, LATER, case_tags=["tag-1"])
    cases = page_of(batch, "cases")

    assert [job.case for job in jobs()] == ["case-1"]

    nothing = alice.post(cases, {}, follow=True)
    held = alice.post(cases, {"case_tags": ["tag-1"]}, follow=True)

    assert said(nothing) == ["Pick case tags or cases to add."]
    assert said(held) == ["The batch holds every case picked already."]

    added = alice.post(cases, {"case_tags": ["tag-2"]}, follow=True)
    batch.refresh_from_db()

    assert said(added) == ["1 case added: 1 trial stored till the batch is run."]
    assert [case["name"] for case in batch.cases] == ["case-1", "case-2"]
    assert batch.tags == ["tag-1", "tag-2"]
    assert [(job.case, job.status) for job in jobs()] == [
        ("case-1", Status.STORED),
        ("case-2", Status.STORED),
    ]

    _ = alice.post(page_of(batch, "run"), {"action": "resume"}, follow=True)
    _ = JobModel.objects.filter(case="case-2").delete()
    batch.cases = batch.cases[:1]
    batch.save()
    queued = alice.post(cases, {"cases": ["case-2"]}, follow=True)

    assert said(queued) == ["1 case added: 1 trial queued behind the batch's."]
    assert {job.status for job in jobs()} == {Status.QUEUED}


def test_a_batch_s_page_follows_it_while_it_is_on_its_way(alice: Client):
    batch = kept(alice)
    page = alice.get(page_of(batch))
    state = alice.get(page_of(batch, "state"))

    assert f'hx-get="{page_of(batch, "state")}"'.encode() in page.content
    assert state.templates[0].name == "portal/batch/state_panel.html"
    assert b"Follow it on the status page" in state.content


def test_another_s_batch_is_theirs_alone(alice: Client, bob: Client):
    batch = kept(alice)

    assert bob.get(page_of(batch, "state")).status_code == 404
    assert bob.post(page_of(batch, "run"), {"action": "rerun"}).status_code == 404
    assert bob.post(page_of(batch, "cases"), {"cases": ["case-1"]}).status_code == 404


def test_the_batches_list_says_where_each_stands(alice: Client, fake: FakeTransport):
    _ = kept(alice)
    _ = worker.run(fake)
    _ = kept(alice)
    _ = kept(alice, LATER)
    listed = alice.get(CHANGELIST).content.decode()

    assert "completed · 2 of 2" in listed
    assert "queued · 0 of 2" in listed
    assert ">stored<" in listed


@pytest.mark.parametrize(
    ("status", "error", "outcome", "reason"),
    [
        (Status.ABORTED, "stopped", "stopped", None),
        (Status.COMPLETED, "ReadTimeout: the stack went quiet", "errored", None),
    ],
)
def test_a_case_that_went_wrong_is_told_once(
    alice: Client,
    fake: FakeTransport,
    status: Status,
    error: str,
    outcome: str,
    reason: str | None,
):
    _ = kept(alice)
    _ = worker.run(fake)
    job = JobModel.objects.get(case="case-2")
    _ = JobModel.objects.filter(pk=job.pk).update(status=status)
    _ = RunModel.objects.filter(pk=job.run_id).update(
        status=RunStatus.ERRORED, error=error
    )

    [ran] = [
        ran for ran in alice.get(PANEL).context["shown"].latest if ran.case == "case-2"
    ]

    assert (ran.outcome, ran.trouble, ran.reason) == (
        outcome,
        True,
        reason or (error if outcome == "errored" else None),
    )
