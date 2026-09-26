# pyright: basic
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.dev.samples import BROKEN_OFF, sample
from chatddx.history.models import RunModel

pytestmark = pytest.mark.django_db

CHANGELIST = reverse("admin:portal_run_changelist")


def page_of(run: RunModel) -> str:
    return reverse("admin:portal_run_change", args=[run.uuid])


def shown(client: Client, run: RunModel) -> Any:
    response = client.get(page_of(run))
    assert response.status_code == 200, response.content

    return response.context["shown"]


def test_the_runs_are_the_owner_s_the_latest_first(alice: Client, bob: Client):
    first, second = (
        sample("alice", "typical", case="case-1"),
        sample("alice", "broken", case="case-1"),
    )
    theirs = sample("bob", "typical", case="case-1")
    listed = alice.get(CHANGELIST).context["cl"].result_list

    assert [run.pk for run in listed] == [second.pk, first.pk]
    assert alice.get(page_of(theirs)).status_code == 404


def test_a_typical_run_s_page_says_how_it_came_out_and_what_it_answered(
    alice: Client,
):
    run = sample("alice", "typical", case="case-1")
    page = shown(alice, run)
    details = {str(detail.label): detail.value for detail in page.details}

    assert (page.outcome, page.trouble) == ("valid", False)
    assert page.description == "plan × qwen3-8b-awq@fake × case-1 (seed 58213)"
    assert details["Case"] == "case-1"
    assert details["Seed"] == "#58213"
    assert details["Stack"] == "qwen3-8b-awq@fake"
    assert details["Tokens"].endswith("over 1 request")
    assert ("reasoning", "default") in page.slices
    assert [view for view, _ in page.views] == [
        "differential",
        "warning",
        "disposition",
        "critical",
    ]
    assert dict(page.views)["differential"][0] == "Biliary colic"
    assert {score.scorer for score in page.scores} == {
        "reciprocal_rank",
        "warning_mentions",
        "disposition_mentions",
    }
    assert [(message.role, message.said) for message in page.messages] == [
        ("user", "case vignette 1"),
        ("assistant", "thinking · the answer"),
    ]


def test_a_broken_run_s_page_shows_everything_that_went_wrong(alice: Client):
    run = sample("alice", "broken", case="case-1")
    page = shown(alice, run)
    details = {str(detail.label): detail for detail in page.details}
    troubled = [message.number for message in page.messages if message.trouble]

    assert (page.outcome, page.trouble) == ("errored", True)
    assert details["Why"].value == f"RemoteProtocolError: {BROKEN_OFF}"
    assert page.scores == []
    # the failed search, the call it didn't take, and the break
    assert troubled == [3, 5, 7]
    assert page.messages[2].said.startswith(
        "web_search → HTTPStatusError: Server error '503 Service Unavailable'"
    )
    assert page.messages[3].said == (
        "thinking · web_search(“infected aortic aneurysm presentation”)"
    )
    # what it got out before the server went away, and what counted nothing
    [text] = [part for part in page.messages[5].parts if part.kind == "text"]
    assert text.text.endswith("masks peritonism, and") and not text.code
    assert page.messages[5].usage is None
    assert page.messages[5].said == "thinking · the answer, unfinished"


def test_a_rich_run_s_page_holds_every_message_and_part(alice: Client):
    run = sample("alice", "rich", case="case-1")
    page = shown(alice, run)
    kinds = [part.kind for message in page.messages for part in message.parts]

    assert (page.outcome, len(page.messages)) == ("valid", 11)
    assert kinds.count("thinking") == 5
    assert kinds.count("call") == 7
    assert kinds.count("return") == 7
    # the instructions once, with the first request, not again with each after
    assert kinds.count("instructions") == 1
    assert page.messages[1].said.startswith(
        "thinking · “Before settling on an exacerbation"
    )
    assert [message.number for message in page.messages if message.trouble] == [5]
    assert page.messages[9].said == "thinking · final_result: the answer"
    assert [exchanged.which for exchanged in page.exchanged] == [
        "request",
        "response",
    ] * 5


def test_what_a_run_sent_and_got_back_comes_as_it_is_opened(alice: Client):
    run = sample("alice", "typical", case="case-1")
    url = reverse("admin:portal_run_exchange", args=[run.uuid, 1, "response"])
    request = alice.get(
        reverse("admin:portal_run_exchange", args=[run.uuid, 1, "request"])
    )
    response = alice.get(url)

    assert b"&quot;chat_template_kwargs&quot;" in request.content
    assert response.content.startswith(b"data: {")
    assert b"[DONE]" in response.content
    assert b'hx-trigger="toggle once"' in alice.get(page_of(run)).content
    assert (
        alice.get(
            reverse("admin:portal_run_exchange", args=[run.uuid, 2, "response"])
        ).status_code
        == 404
    )


def test_a_run_is_linked_from_its_case_s_page(alice: Client):
    run = sample("alice", "typical", case="case-1")
    case = reverse("admin:portal_case_changelist")
    row = alice.get(f"{case}?q=case-1").context["cl"].result_list[0]

    assert (
        page_of(run).encode()
        in alice.get(reverse("admin:portal_case_change", args=[row.pk])).content
    )
