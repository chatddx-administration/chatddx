# pyright: basic
from typing import Any
from urllib.parse import urlencode

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.bench.bench import Bench, Trial
from chatddx.bench.sending import Handed, Sending
from chatddx.conftest import Recommit
from chatddx.dev.fake_vllm import FakeTransport
from chatddx.django.portal import cases
from chatddx.django.portal.case_admin import BACK, ONTO
from chatddx.history.models import ConversationContext, RunModel, ScoreModel
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import CaseBranchDetails, CaseTrailIn
from chatddx.repo.store.branch import commit

pytestmark = pytest.mark.django_db

FAKE = "qwen3-8b-awq@fake"
ADD = reverse("admin:portal_case_add")
CHANGELIST = reverse("admin:portal_case_changelist")
CHECK = reverse("admin:portal_case_check")

# case-1 as the seed gives it to alice: the test inventory's
CASE_1 = {
    "name": "case-1",
    "language": "en",
    "vignette": "case vignette 1",
    "diagnosis_text": "Fake diagnosis B",
    "diagnosis_pattern": "fake & diagnosis & (b | 2)",
    "warning_pattern": "acute & warning",
    "disposition_pattern": "admit*",
    "tags": ["tag-1", "tag-2"],
}


def versions(name: str, owner: str = "alice") -> list[CaseBranchModel]:
    return list(
        CaseBranchModel.objects.filter(owner__name=owner, name=name).order_by(
            "timestamp", "id"
        )
    )


def head(name: str, owner: str = "alice") -> CaseBranchModel:
    return versions(name, owner)[-1]


def page_of(row: CaseBranchModel, of: str = "change") -> str:
    return reverse(f"admin:portal_case_{of}", args=[row.pk])


def opened(client: Client, name: str = "case-1") -> dict[str, Any]:
    """The case's page, as its form holds it: what a save posts, unchanged."""
    form = client.get(page_of(head(name))).context["form"]

    return {
        field.html_name: form.initial.get(field.name, field.initial)
        for field in form
        if form.initial.get(field.name, field.initial) not in (None, False)
    }


def said(response: Any) -> list[str]:
    return [str(message) for message in response.context["messages"]]


def ran(owner: str = "alice", case: str = "case-1") -> RunModel:
    """free-text on the owner's case, sent and written down, and scored."""
    bench = Bench(owner, FakeTransport())
    ready = bench.ready(bench.cell_of("free-text", FAKE))
    [found] = [each for each in bench.cases() if each.name == case]
    sending = Sending(bench, Trial.on(ready, found, 42), ConversationContext.WORKER)

    with Handed(sending.events()) as handed:
        for _ in handed:
            pass

    run = sending.written().run
    assert run is not None

    return run


def test_the_list_is_of_the_owner_s_cases(
    alice: Client, bob: Client, recommit: Recommit
):
    recommit("case", "case-1", name="archive-case", collaborators=["alice"])
    recommit("case", "case-2", name="bob-case", owner="bob")
    response = alice.get(CHANGELIST)
    listed = {case.name for case in response.context["cl"].result_list}

    assert response.status_code == 200
    assert listed == {"case-1", "case-2"}
    assert {case.owner.name for case in response.context["cl"].result_list} == {"alice"}


def test_the_list_says_what_each_case_still_wants(alice: Client, recommit: Recommit):
    recommit(
        "case",
        "case-2",
        owner="alice",
        targets={"diagnosis": {"text": "nothing", "pattern": "nothing & (listed"}},
    )

    def listed(query: str) -> set[str]:
        response = alice.get(f"{CHANGELIST}?{query}")
        return {case.name for case in response.context["cl"].result_list}

    assert listed("wanting=text") == {"case-1", "case-2"}
    assert listed("wanting=unread") == {"case-2"}
    assert listed("tag=tag-1") == {"case-1"}
    assert b"doesn&#x27;t parse: Diagnosis" in alice.get(CHANGELIST).content


def test_a_blank_case_saved_is_a_new_case(alice: Client):
    response = alice.post(
        ADD,
        {
            "name": " mine ",
            "language": "sv",
            "vignette": "  A new vignette.\r\nOn two lines.  ",
            "diagnosis_text": "  ",
            "diagnosis_pattern": " new & vignette ",
            "warning_none": "on",
            "tags": ["mine", "tag-1"],
        },
        follow=True,
    )
    [mine] = versions("mine")

    assert response.redirect_chain == [(page_of(mine), 302)]
    assert said(response) == ["Saved as a new case, mine."]
    assert mine.trail.vignette == "A new vignette.\nOn two lines."
    assert mine.details == {
        "language": "sv",
        "targets": {
            "diagnosis": {"text": None, "pattern": "new & vignette"},
            "warning": False,
        },
        "deleted": False,
    }
    assert sorted(tag.name for tag in mine.tags.all()) == ["mine", "tag-1"]


def test_what_can_t_be_saved_comes_back_as_the_form(alice: Client):
    response = alice.post(
        ADD,
        {
            "name": "one/two",
            "vignette": "   ",
            "diagnosis_pattern": "fake & (diagnosis",
            "warning_none": "on",
            "warning_text": "a warning",
        },
    )
    errors = {
        field: " ".join(errors)
        for field, errors in response.context["form"].errors.items()
    }

    assert response.status_code == 200
    assert "the repl parts an owner from a name by it" in errors["name"]
    assert "A case is its vignette" in errors["vignette"]
    assert errors["diagnosis_pattern"] == (
        "Doesn't parse: a '(' in 'fake & (diagnosis' is never closed"
    )
    assert "None expected takes no text or pattern" in errors["warning_none"]
    assert not versions("one/two")


def test_a_save_makes_one_new_version_and_moves_the_head(alice: Client):
    before = head("case-1")
    asked = opened(alice) | {"diagnosis_text": "Fake diagnosis B, as written"}
    response = alice.post(page_of(before), asked, follow=True)
    first, second = versions("case-1")

    assert first.pk == before.pk
    assert response.redirect_chain == [(page_of(second), 302)]
    assert said(response) == ["Saved as version 2 of case-1."]
    assert second.details["targets"]["diagnosis"]["text"] == (
        "Fake diagnosis B, as written"
    )
    assert second.trail_id == first.trail_id
    assert sorted(tag.name for tag in second.tags.all()) == ["tag-1", "tag-2"]


def test_a_save_of_what_is_there_already_makes_no_version(alice: Client):
    row = head("case-1")
    unchanged = alice.post(page_of(row), opened(alice), follow=True)
    tagged = alice.post(page_of(row), opened(alice) | {"tags": ["tag-1"]}, follow=True)

    assert said(unchanged) == ["Nothing changed: case-1 stays at version 1."]
    assert said(tagged) == [
        "Its tags are saved, and nothing else changed: case-1 stays at version 1."
    ]
    assert versions("case-1") == [row]
    assert [tag.name for tag in row.tags.all()] == ["tag-1"]


def test_a_vignette_is_as_it_was_but_for_the_whitespace_around_it(alice: Client):
    # as the archive's are, read from files written with CRLF
    _ = commit(
        CaseTrailIn(vignette="case vignette 3,\r\non two lines\r\n"),
        CaseBranchDetails.model_validate({"name": "spaced", "owner": "alice"}),
    )
    row = head("spaced")
    # as a browser posts it back
    asked = opened(alice, "spaced") | {
        "vignette": "  case vignette 3,\r\non two lines \r\n\r\n"
    }

    _ = alice.post(page_of(row), asked | {"language": "sv"})

    assert len(versions("spaced")) == 2
    assert head("spaced").trail_id == row.trail_id


def test_a_new_name_is_a_new_case_and_the_old_one_stays(alice: Client):
    row = head("case-1")
    response = alice.post(
        page_of(row), opened(alice) | {"name": "case-one"}, follow=True
    )
    [renamed] = versions("case-one")
    sharers = response.context["sharers"]

    assert said(response) == ["Saved as a new case, case-one."]
    assert versions("case-1") == [row]
    assert renamed.trail_id == row.trail_id
    # the two hold one vignette: the page says so, and offers to untag the old
    assert [(sharer.name, sharer.own, sharer.tagged) for sharer in sharers] == [
        ("case-1", True, True)
    ]
    assert b"Take its tags off" in response.content

    untag = alice.post(page_of(row, "untag"), {"next": page_of(renamed)}, follow=True)

    assert said(untag) == ["case-1 has no tags now: batches by tag pass it by."]
    assert not row.tags.exists()
    assert versions("case-1") == [row]


def test_saving_onto_another_case_asks_first_and_the_tags_come_along(
    alice: Client,
):
    target = head("case-2")
    asked = opened(alice) | {"name": "case-2"}
    asking = alice.post(page_of(head("case-1")), asked)

    assert asking.templates[0].name == "portal/case/confirmation.html"
    assert asking.context["theirs"].row.pk == target.pk
    assert asking.context["said"].line == (
        "Saving makes version 2 of case-2, another case of yours, replacing its "
        + "vignette and targets."
    )
    assert "Vignette" in [str(change.label) for change in asking.context["changes"]]
    assert versions("case-2") == [target]

    back = alice.post(page_of(head("case-1")), asked | {BACK: "1"})

    assert back.templates[0].name == "portal/case/change_form.html"
    assert back.context["form"]["name"].value() == "case-2"

    done = alice.post(
        page_of(head("case-1")), asked | {ONTO: str(target.pk)}, follow=True
    )
    first, second = versions("case-2")

    assert said(done) == ["Saved onto case-2, as its version 2."]
    assert first.pk == target.pk
    assert second.trail.vignette == "case vignette 1"
    assert sorted(tag.name for tag in second.tags.all()) == ["tag-1", "tag-2"]


def test_a_page_whose_case_moved_on_is_told_and_saves_on_top_when_again(
    alice: Client,
):
    stale = opened(alice)
    _ = alice.post(page_of(head("case-1")), stale | {"language": "sv"}, follow=True)
    asked = stale | {"diagnosis_text": "the stale page's"}

    told = alice.post(page_of(head("case-1")), asked)

    assert told.templates[0].name == "portal/case/change_form.html"
    assert "case-1 has a version 2, saved" in said(told)[0]
    assert len(versions("case-1")) == 2

    again = told.context["form"].data.dict() | {"tags": asked["tags"]}
    _ = alice.post(page_of(head("case-1")), again)
    last = head("case-1")

    assert len(versions("case-1")) == 3
    assert last.details["targets"]["diagnosis"]["text"] == "the stale page's"


def test_what_saving_does_is_said_as_the_name_is_typed(alice: Client):
    _ = alice.post(
        page_of(head("case-2")), opened(alice, "case-2") | {"language": "sv"}
    )

    def line(**asked: Any) -> str:
        return alice.post(CHECK, asked).context["said"].line

    assert line(name="case-1", edited="case-1") == (
        "Saving makes version 2 of this case."
    )
    assert line(name="case-1", edited="case-1", since="1") == (
        "Saving makes version 2 of this case, from version 1."
    )
    assert line(name="new", edited="case-1") == (
        "Saving makes a new case, new, and this one stays as it is."
    )
    assert line(name="case-2", edited="case-1") == (
        "Saving makes version 3 of case-2, another case of yours, replacing its "
        + "vignette and targets."
    )
    assert line(name="") == "Name the case to save it."

    response = alice.post(CHECK, {"name": "Case-1"})

    assert response.context["said"].capitals == ["case-1"]
    assert b'id="case-save-label" hx-swap-oob="true"' in response.content


def test_a_vignette_another_holds_is_said_so_with_the_name_to_take(
    alice: Client, recommit: Recommit
):
    recommit("case", "case-2", name="shared", collaborators=["alice"])
    response = alice.post(CHECK, {"name": "mine", "vignette": "case vignette 2\n"})
    sharers = response.context["sharers"]

    assert [(sharer.name, sharer.owner, sharer.own) for sharer in sharers] == [
        ("case-2", "alice", True),
        ("shared", "archive", False),
    ]
    assert b"archive's shared has this vignette" in response.content
    assert b'data-name="shared"' in response.content
    # named as the shared one is, it takes its place
    named = alice.post(CHECK, {"name": "shared", "vignette": "case vignette 2"})

    assert [sharer.name for sharer in named.context["sharers"]] == ["case-2"]


def test_an_earlier_version_is_read_and_edited_from(alice: Client):
    first = head("case-1")
    _ = alice.post(
        page_of(first),
        opened(alice) | {"vignette": "case vignette 1, told again", "language": "sv"},
    )
    read = alice.get(page_of(first))

    assert read.context["form"] is None
    assert read.context["version"].number == 1
    assert b"version 1 of 2" in read.content
    assert b"Edit from here" in read.content

    changed = alice.get(page_of(head("case-1"))).context["changes"]

    assert [str(change.label) for change in changed] == ["Vignette", "Language"]
    assert ("new", ", told again") in changed[0].words

    edited = alice.get(f"{page_of(first)}?edit")
    form = edited.context["form"]

    assert form.initial["since"] == 1
    assert form.initial["vignette"] == "case vignette 1"
    assert form.initial["head"] == head("case-1").pk

    asked = {
        field.html_name: form.initial.get(field.name)
        for field in form
        if form.initial.get(field.name) not in (None, False)
    }
    response = alice.post(page_of(first), asked, follow=True)

    assert said(response) == ["Saved as version 3 of case-1."]
    assert head("case-1").trail_id == first.trail_id
    assert head("case-1").details["language"] == "en"


def test_deleting_the_head_is_an_undo(alice: Client):
    first = head("case-1")
    _ = alice.post(page_of(first), opened(alice) | {"language": "sv"})
    second = head("case-1")

    asked = alice.get(page_of(second, "delete"))
    response = alice.post(page_of(second, "delete"), follow=True)

    assert b"Version 2 of case-1 goes for good." in asked.content
    assert said(response) == [
        "Version 2 of case-1 is deleted. Version 1 is its head again."
    ]
    assert versions("case-1") == [first]


def test_a_version_scored_against_can_t_be_deleted(alice: Client):
    _ = ran()
    first = head("case-1")
    _ = alice.post(page_of(first), opened(alice) | {"language": "sv"})

    asked = alice.get(page_of(first, "delete"))
    _ = alice.post(page_of(first, "delete"))

    assert asked.context["can"] is False
    assert b"scores were held to its targets" in asked.content
    assert len(versions("case-1")) == 2


def test_a_case_nothing_read_is_deleted_for_good(alice: Client):
    _ = alice.post(ADD, {"name": "mine", "vignette": "mine alone"})
    [mine] = versions("mine")

    asked = alice.get(page_of(mine, "delete"))
    response = alice.post(page_of(mine, "delete"), follow=True)

    assert b"nothing has read it: deleting it deletes mine for good" in asked.content
    assert said(response) == ["mine is gone for good: nothing had read it."]
    assert not versions("mine")


def test_a_case_something_reads_is_taken_out_of_sight_and_back(alice: Client):
    run = ran()
    response = alice.post(
        CHANGELIST,
        {
            "action": "delete_cases",
            "_selected_action": [head("case-1").pk],
            "post": "yes",
        },
        follow=True,
    )
    gone = head("case-1")
    bench = Bench("alice")

    assert "0 gone for good" in said(response)[0]
    assert gone.details["deleted"] is True
    assert "case-1" not in {case.name for case in response.context["cl"].result_list}
    assert "case-1" not in {
        case.name for case in Bench("alice", own=("case",)).cases(["tag-1"])
    }
    # its runs keep its name
    assert bench.name_of("case", run.trial.case) == "case-1"

    back = alice.post(page_of(gone, "restore"), follow=True)

    assert said(back) == ["case-1 is back."]
    assert len(versions("case-1")) == 1
    assert "case-1" in {case.name for case in Bench("alice").cases(["tag-1"])}


def test_the_delete_action_asks_first(alice: Client):
    _ = ran()
    response = alice.post(
        CHANGELIST,
        {
            "action": "delete_cases",
            "_selected_action": [head("case-1").pk, head("case-2").pk],
        },
    )

    assert response.templates[0].name == "portal/case/delete_cases.html"
    assert b"out of sight, kept for what reads it" in response.content
    assert b"gone for good: nothing has read it" in response.content
    assert not head("case-1").details["deleted"]


def test_a_case_s_page_shows_its_runs_with_the_scores_for_its_targets_now(
    alice: Client,
):
    _ = ran()
    row = head("case-1")
    response = alice.get(page_of(row))
    runs = response.context["runs"]

    assert runs.total == 1
    assert runs.scorers == ["first_mention", "reciprocal_rank"]
    assert runs.rows[0].scores == ["17", "0.5"]
    assert runs.outstanding == 0

    # a pattern changed: the run's score for it is outstanding, the old one aside
    asked = opened(alice) | {"diagnosis_pattern": "fake & diagnosis & a"}
    _ = alice.post(page_of(row), asked)
    runs = alice.get(page_of(head("case-1"))).context["runs"]

    assert runs.rows[0].scores == ["outstanding", "outstanding"]
    assert runs.outstanding == 1

    scored = alice.post(
        page_of(head("case-1"), "score"), {"next": page_of(head("case-1"))}, follow=True
    )

    assert said(scored) == ["2 scores made."]
    assert alice.get(page_of(head("case-1"))).context["runs"].rows[0].scores == [
        "0",
        "1",
    ]
    assert ScoreModel.objects.filter(owner__name="alice").count() == 4


def test_another_owner_s_case_is_not_found(alice: Client, bob: Client):
    theirs = head("case-1", "bob")

    assert alice.get(page_of(theirs)).status_code == 404
    assert alice.post(page_of(theirs, "delete")).status_code == 404


def test_a_case_s_page_leads_to_the_cases_beside_it_in_its_list(alice: Client):
    def neighbours(name: str, filters: str) -> tuple[Any, Any]:
        query = urlencode({"_changelist_filters": filters})
        context = alice.get(f"{page_of(head(name))}?{query}").context
        return context["previous_case"], context["next_case"]

    first, second = (
        neighbours("case-1", "wanting=text"),
        neighbours("case-2", "wanting=text"),
    )

    assert first[0] is None and first[1][0] == "case-2"
    assert second[0][0] == "case-1" and second[1] is None
    # the list's filters ride along
    assert "_changelist_filters=wanting%3Dtext" in first[1][1]
    assert neighbours("case-1", "tag=tag-1") == (None, None)


def test_a_vignette_rewritten_altogether_is_said_so():
    rewritten = cases.vignette_change(
        "A fall at home.", "Chest pain at rest, sweating."
    )
    edited = cases.vignette_change("case vignette 1", "case vignette 1, told again")

    assert rewritten.whole and not rewritten.words
    assert not edited.whole
    assert edited.words == [("kept", "case vignette 1"), ("new", ", told again")]
