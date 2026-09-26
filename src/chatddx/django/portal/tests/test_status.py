# pyright: basic
import re
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from chatddx.dev.fake_vllm import FakeTransport
from chatddx.django.portal.admin import CONFIRM
from chatddx.django.portal.models import BatchModel
from chatddx.history.models import RunModel, RunStatus
from chatddx.worker import control, worker
from chatddx.worker.models import QueuedModel, Status, Stopping, WorkerStateModel

pytestmark = pytest.mark.django_db

ADD = reverse("admin:portal_batch_add")
STATUS = reverse("admin:portal_batch_status")
PANEL = reverse("admin:portal_batch_status_panel")
CONTROL = reverse("admin:portal_batch_status_control")

FREE_TEXT = {
    "configuration": "free-text",
    "stack": "qwen3-8b-awq@fake",
    "case_tags": ["tag-2"],
    "seed": "42",
}


def kept(client: Client, **asked: Any) -> BatchModel:
    """A batch planned, confirmed and kept: its trials in the worker's queue."""
    response = client.post(ADD, FREE_TEXT | asked | {CONFIRM: "1"})
    assert response.status_code == 302, response.content

    return BatchModel.objects.order_by("-pk").first()  # pyright: ignore[reportReturnType]


def tabs(response: Any) -> list[tuple[str, bool]]:
    """The Batches' tabs on a page: where each leads, and whether it is the one."""
    [nav] = re.findall(
        r'<nav id="tabs-items".*?</nav>', response.content.decode(), re.DOTALL
    )

    return [
        (href, "active" in classes)
        for href, classes in re.findall(r'<a href="([^"]*)" class="([^"]*)"', nav)
    ]


def under_way(case: str, tokens: int = 0) -> None:
    """`case` taken up by a worker at work: seen just now, its beat fresh."""
    now = timezone.now()
    _ = WorkerStateModel.objects.update_or_create(pk=1, defaults={"seen": now})
    _ = QueuedModel.objects.filter(case=case).update(
        status=Status.RUNNING, started=now, beat=now, tokens=tokens
    )


def pressed(client: Client, action: str, htmx: bool = True) -> Any:
    headers = {"HX-Request": "true"} if htmx else {}
    return client.post(CONTROL, {"action": action}, headers=headers)


def test_a_batch_kept_puts_its_trials_in_the_worker_s_queue(alice: Client):
    batch = kept(alice, reasoning=["default", "off"])
    queued = list(QueuedModel.objects.order_by("pk"))

    assert [(item.label, item.case) for item in queued] == [
        ("free-text", "case-1"),
        ("free-text", "case-2"),
        ("free-text+reasoning=off", "case-1"),
        ("free-text+reasoning=off", "case-2"),
    ]
    assert {(item.batch, item.owner.name, item.status) for item in queued} == {
        (batch.uuid, "alice", Status.QUEUED)
    }
    assert [item.fingerprint for item in queued[::2]] == [
        cell["fingerprint"] for cell in batch.cells
    ]


def test_a_batch_kept_leads_to_the_status_page(alice: Client):
    response = alice.post(ADD, FREE_TEXT | {CONFIRM: "1"}, follow=True)

    assert f'href="{STATUS}">Follow them on the status page.</a>'.encode() in (
        response.content
    )


def test_the_status_page_is_one_of_the_batches(alice: Client):
    changelist = reverse("admin:portal_batch_changelist")
    response = alice.get(STATUS)

    assert response.status_code == 200
    assert tabs(response) == [(changelist, False), (STATUS, True)]
    assert tabs(alice.get(changelist)) == [(changelist, True), (STATUS, False)]
    assert f'hx-get="{PANEL}"'.encode() in response.content
    assert b'hx-trigger="every 1s"' in response.content
    # a status of the worker's, whatever batch its cases came from
    assert b"Nothing has been queued yet." in response.content


def test_the_status_counts_the_drain_and_shows_the_cases_taken_up_last(
    alice: Client, fake: FakeTransport
):
    batch = kept(alice)
    _ = worker.run(fake)
    response = alice.get(PANEL)
    shown = response.context["shown"]

    assert shown.counted == "0 running · 2 completed · 2 total"
    assert [(ran.case, ran.cell, ran.outcome) for ran in shown.latest] == [
        ("case-2", "free-text × qwen3-8b-awq@fake", "completed"),
        ("case-1", "free-text × qwen3-8b-awq@fake", "completed"),
    ]
    assert dict(shown.latest[0].scores) == {
        "first_mention": "—",
        "reciprocal_rank": "0",
    }
    assert b"Idle: nothing is queued." in response.content
    assert b"reciprocal_rank 0" in response.content

    changelist = alice.get(reverse("admin:portal_batch_changelist"))

    assert b"2 of 2" in changelist.content
    assert batch.trials == 2


@pytest.mark.parametrize(
    ("error", "outcome", "reason"),
    [
        ("stopped", "stopped", None),
        (
            "ReadTimeout: the stack went quiet",
            "errored",
            "ReadTimeout: the stack went quiet",
        ),
    ],
)
def test_a_case_that_went_wrong_is_told_once(
    alice: Client, fake: FakeTransport, error: str, outcome: str, reason: str | None
):
    _ = kept(alice)
    _ = worker.run(fake)
    item = QueuedModel.objects.get(case="case-2")
    _ = RunModel.objects.filter(pk=item.run_id).update(
        status=RunStatus.ERRORED, error=error
    )

    [latest, _] = alice.get(PANEL).context["shown"].latest

    assert (latest.case, latest.outcome, latest.trouble, latest.reason) == (
        "case-2",
        outcome,
        True,
        reason,
    )


def test_the_case_running_is_shown_with_its_tally_live(alice: Client):
    _ = kept(alice)
    under_way("case-1", tokens=12)
    response = alice.get(PANEL)

    assert response.context["shown"].running.case == "case-1"
    assert response.context["shown"].counted == "1 running · 0 completed · 2 total"
    assert b"~12 tokens" in response.content
    assert b"Running." in response.content


def test_the_worker_not_seen_is_said(alice: Client):
    response = alice.get(PANEL)

    assert b"The worker isn&#x27;t running" in response.content


def test_pause_resumes_as_it_is_pressed_again(alice: Client):
    paused = pressed(alice, "pause")

    assert paused.status_code == 200
    assert control.state().paused
    assert b'value="resume"' in paused.content

    resumed = pressed(alice, "resume", htmx=False)

    assert resumed.status_code == 302 and resumed["Location"] == STATUS
    assert not control.state().paused


def test_stop_once_waits_for_the_case_under_way_and_twice_stops_it(alice: Client):
    _ = kept(alice)
    under_way("case-1")

    once = pressed(alice, "stop")

    assert control.state().stopping == Stopping.AFTER
    assert b"Stop now" in once.content
    assert b"Stopping after this case" in once.content

    twice = pressed(alice, "stop")

    assert control.state().stopping == Stopping.NOW
    assert b"Stopping now." in twice.content
    assert b"disabled" in twice.content


def test_stop_with_no_case_under_way_takes_the_queue_out(alice: Client):
    _ = kept(alice)

    response = pressed(alice, "stop")

    assert {item.status for item in QueuedModel.objects.all()} == {Status.CANCELLED}
    assert response.context["shown"].counted == (
        "0 running · 0 completed · 2 total · 2 cancelled"
    )
    assert response.context["shown"].cancelled_share == "100.00"


def test_the_controls_take_a_post(alice: Client):
    assert alice.get(CONTROL).status_code == 405
