import json
import re
from typing import Any
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

from chatddx.api.test.helpers import body, family
from chatddx.portal.test.helpers import props, ran_template, run_title, shown

__all__ = ["ran_template"]


@pytest.mark.slow
def test_review_opens_the_first_case_of_the_list_and_keeps_its_tag(
    signed: TestClient,
) -> None:
    [first, *_] = signed.get("/api/families").json()
    got = signed.get("/review")
    assert (got.status_code, got.headers["location"]) == (303, f"/review/{first['id']}")
    [swedish, *_] = signed.get("/api/families", params={"tag": "swedish"}).json()
    got = signed.get("/review", params={"tag": "swedish"})
    assert got.headers["location"] == f"/review/{swedish['id']}?tag=swedish"
    page = shown(signed, "/review?tag=nothing-tagged-so")
    assert "No case to review tagged nothing-tagged-so." in page


@pytest.mark.slow
def test_a_case_is_reviewed_with_what_is_expected_and_not_what_reads_it(
    signed: TestClient,
) -> None:
    noted = family(signed, "noted")
    page = shown(signed, f"/review/{noted['id']}")
    vignette = signed.get(f"/api/families/{noted['id']}/vignette").json()["text"]
    assert escape(vignette.strip().splitlines()[0]) not in page
    assert f'href="/cases/{noted["id"]}/vignette"' in page

    [case] = signed.get(f"/api/families/{noted['id']}").json()["cases"]
    [expected] = case["expectations"]
    for note in expected["data"]["notes"]:
        assert escape(note["comment"]) in page

    scorers = signed.get("/api/threads", params={"kind": "scorer"}).json()
    judged = next(t for t in scorers if t["name"] == "judged")
    held = signed.get(f"/api/components/{judged['head']['digest']}").json()["body"]
    for v in held["views"]:
        assert escape(v["expectation"]) not in page
    assert (
        'aria-label="Read with"' not in page
        and f'href="/scoring/{judged["id"]}"' not in page
    )
    schema = signed.get(f"/api/components/{expected['expectation_schema']}").json()
    assert f"under {schema['title']}" not in page


def noted_schema(signed: TestClient, noted: dict[str, Any]) -> str:
    [case] = signed.get(f"/api/families/{noted['id']}").json()["cases"]
    return case["expectations"][0]["expectation_schema"]


@pytest.mark.slow
def test_review_shows_nothing_of_what_ran_the_case(
    signed: TestClient,
) -> None:
    noted = family(signed, "noted")
    runs = signed.get("/api/runs", params={"reaching": noted["case"]}).json()
    assert runs
    page = shown(signed, f"/review/{noted['id']}")
    assert (
        "data-drawer" not in page and "/runs/" not in page and "evaluating" not in page
    )
    for r in runs:
        assert escape(run_title(r)) not in page
    listed = page.split(f'href="/review/{noted["id"]}"', 1)[1].split("</a>", 1)[0]
    assert "tabular-nums" not in listed and " time" not in listed
    given = props(page)
    assert set(given) == {
        "family",
        "case",
        "expected",
        "appendices",
        "back",
        "schema",
        "measure",
        "about",
    }
    assert given["schema"] == noted_schema(signed, noted)
    assert given["measure"] == {
        "fields": ["diagnosis", "warning", "disposition", "dont_miss"],
        "field": None,
    }
    assert f'action="/review/{noted["id"]}/runs"' in page
    assert "<div data-slides data-review class" in page
    measuring = shown(signed, f"/review/{noted['id']}?measure=warning")
    assert props(measuring)["measure"]["field"] == "warning"
    assert "<div data-slides data-review data-slid class" in measuring
    unread = shown(signed, f"/review/{noted['id']}?measure=notes")
    assert props(unread)["measure"]["field"] is None


@pytest.mark.slow
def test_a_family_s_other_case_shows_its_appendices(signed: TestClient) -> None:
    whitespace = family(signed, "whitespace")
    cases = signed.get(f"/api/families/{whitespace['id']}").json()["cases"]
    labs = next(c for c in cases if c["appendices"])
    page = shown(signed, f"/review/{whitespace['id']}")
    assert "<article" not in page and "Appendices, in order" not in page
    branch = f'href="/review/{whitespace["id"]}?{urlencode({"case": labs["case"]})}"'
    assert page.count(branch) == 1
    listed = page.split(branch, 1)[1].split("</a>", 1)[0]
    assert ">labs</span>" in listed and 'aria-current="page"' not in listed
    noted = family(signed, "noted")
    under = page.split(f'href="/review/{noted["id"]}"', 1)[1].split("</li>", 1)[0]
    assert "case=" not in under
    page = shown(signed, f"/review/{whitespace['id']}?case={labs['case']}")
    assert "CRP 180 mg/L, leukocytes 16." in page
    tree = page.split('<nav aria-label="Cases">', 1)[1]
    listed = tree.split(branch, 1)[1].split("</a>", 1)[0]
    assert listed.startswith(' aria-current="page"')
    assert props(page)["case"] == labs["case"]
    [appendix] = props(page)["appendices"]
    assert appendix["thread"] is None
    assert f'action="/review/{whitespace["id"]}/delete"' not in page
    got = signed.post(f"/review/{whitespace['id']}/delete", data={"case": labs["case"]})
    assert got.status_code == 404


@pytest.mark.slow
def test_the_list_holds_each_tag_picked_and_any_language_picked(
    signed: TestClient,
) -> None:
    every = signed.get("/api/families").json()
    noted = family(signed, "noted")

    def listed(query: str) -> set[int]:
        page = shown(signed, f"/review/{noted['id']}?{query}")
        held = page.split('aria-label="Cases"', 1)[1].split("</ol>", 1)[0]
        assert "<kbd>" not in page and "<summary" not in held
        items = re.findall(
            r'<li data-tags=[^>]*?( hidden)?>\s*<a href="/review/(\d+)', held
        )
        assert len(items) == len(every)
        return {int(id) for hidden, id in items if not hidden}

    both = {f["id"] for f in every if {"targets", "swedish"} <= set(f["tags"])}
    targets = {f["id"] for f in every if "targets" in f["tags"]}
    assert both and both < targets
    assert listed("tag=targets") == targets
    assert listed("tag=targets&tag=swedish") == both
    languages = {f["language"] for f in every if f["language"]}
    assert len(languages) > 1
    for language in languages:
        spoken = {f["id"] for f in every if f["language"] == language}
        assert listed(f"language={language}") == spoken
        assert listed(f"tag=targets&language={language}") == spoken & targets
    assert listed(f"language={'&language='.join(languages)}") == {
        f["id"] for f in every if f["language"]
    }

    page = shown(signed, f"/review/{noted['id']}?tag=targets&tag=swedish")
    assert props(page).keys() >= {"about"} and "next" not in props(page)
    assert re.search(
        r'tag=targets" data-tag="swedish" aria-current="true" class="view">swedish</a>',
        page,
    )
    assert re.search(
        r'tag=swedish" data-tag="targets" aria-current="true" class="view">targets</a>',
        page,
    )


@pytest.mark.slow
def test_what_review_can_t_find_is_not_found(signed: TestClient) -> None:
    noted = family(signed, "noted")
    for query in ("case=sha256:nothing", "schema=sha256:nothing"):
        got = signed.get(f"/review/{noted['id']}?{query}")
        assert got.status_code == 404, query
        assert got.headers["content-type"].startswith("text/html")
    assert signed.get("/review/0").status_code == 404


@pytest.mark.slow
def test_the_expectation_is_edited_in_place_with_its_versions_alone(
    signed: TestClient,
) -> None:
    noted = family(signed, "noted")
    given = props(shown(signed, f"/review/{noted['id']}?tag=targets"))
    expected = given["expected"]
    editor = expected["editor"]
    [case] = signed.get(f"/api/families/{noted['id']}").json()["cases"]
    [held] = case["expectations"]
    assert (editor["mode"], editor["case"], editor["data"]) == (
        "edit",
        noted["case"],
        held["data"],
    )
    assert expected["history"][-1]["digest"] == held["expectation"]
    assert set(expected) == {"editor", "history"}
    assert given["back"] == f"/review/{noted['id']}?tag=targets"


@pytest.mark.slow
def test_an_island_is_given_its_json_in_the_order_it_is_stored(
    signed: TestClient,
) -> None:
    noted = family(signed, "noted")
    expected = props(shown(signed, f"/review/{noted['id']}"))["expected"]
    editor = expected["editor"]
    digest = expected["history"][-1]["digest"]
    expectation = signed.get(f"/api/components/{digest}").json()
    schema = signed.get(f"/api/components/{editor['schema']}").json()
    assert json.dumps(editor["data"]) == json.dumps(expectation["body"]["data"])
    assert json.dumps(editor["json_schema"]) == json.dumps(
        schema["body"]["json_schema"]
    )


@pytest.mark.slow
def test_what_is_shared_to_take_is_shown_with_its_take(signed: TestClient) -> None:
    noted = family(signed, "noted")
    [expected] = signed.get(f"/api/families/{noted['id']}").json()["cases"][0][
        "expectations"
    ]
    query = {"kind": "expectation", "owner": "alice"}
    mine = next(
        t
        for t in signed.get("/api/threads", params=query).json()
        if t["head"]["digest"] == expected["expectation"]
    )
    page = shown(signed, f"/review/{noted['id']}")
    assert "data-offered" not in page
    assert signed.patch(f"/api/threads/{mine['id']}", json={"deleted": True}).is_success
    [shared] = signed.get(f"/api/families/{noted['id']}").json()["cases"][0][
        "expectations"
    ][0]["shared"]
    page = shown(signed, f"/review/{noted['id']}")
    offered = page.split(f'data-offered="{shared["id"]}"', 1)[1]
    offered = offered.split('id="review-expected"', 1)[0]
    assert f'action="/threads/{shared["id"]}/take"' in offered
    for note in expected["data"]["notes"]:
        assert escape(note["comment"]) in offered


@pytest.mark.slow
def test_a_case_branches_off_the_one_it_adds_an_appendix_to_and_goes_with_it(
    signed: TestClient,
) -> None:
    crlf = family(signed, "crlf")
    back = f"/review/{crlf['id']}?tag=targets"

    def built(*appendices: str) -> dict[str, Any]:
        cases = signed.get(f"/api/families/{crlf['id']}").json()["cases"]
        return next(c for c in cases if c["appendices"] == list(appendices))

    def written(name: str, text: str, *under: str) -> tuple[str, str]:
        given = {"name": name, "text": text}
        got = signed.post(f"/api/families/{crlf['id']}/appendices", json=given)
        assert got.status_code == 201
        made = got.json()["head"]["digest"]
        appendices = {"appendices": [*under, made]}
        got = signed.post(f"/api/families/{crlf['id']}/cases", json=appendices)
        assert got.status_code == 201
        return made, f"{back}&{urlencode({'case': got.json()['case']})}"

    default = built()
    ultrasound, at = written("ultrasound", "Gallstones on ultrasound.")
    alone = built(ultrasound)
    page = shown(signed, at)
    assert "Gallstones on ultrasound." in page
    assert "f.appendices" not in page and "owned by" not in page
    held = page.split('id="review-appendices"', 1)[1].split("</section>", 1)[0]
    assert "<article" in held and "/threads/" not in held and "<form" not in held
    assert f'action="/review/{crlf["id"]}/delete"' in page
    given = props(page)
    [appendix] = given["appendices"]
    assert appendix["digest"] == ultrasound and appendix["thread"] is not None
    editor = given["expected"]["editor"]
    assert (editor["mode"], editor["case"]) == ("new", alone["case"])
    assert editor["data"] == default["expectations"][0]["data"]

    labs, again = written("labs", "Bilirubin 40.", ultrasound)
    both = built(ultrasound, labs)["case"]
    assert again == f"{back}&{urlencode({'case': both})}"
    tree = shown(signed, again).split('<nav aria-label="Cases">', 1)[1]
    branch = f'href="/review/{crlf["id"]}?{urlencode({"case": both})}'
    listed = tree.split(branch, 1)[1].split("</a>", 1)[0]
    assert ">labs</span>" in listed and "ultrasound" not in listed

    def deleted(case: str) -> str:
        got = signed.post(
            f"/review/{crlf['id']}/delete", data={"case": case, "back": again}
        )
        assert got.status_code == 303
        return got.headers["location"]

    assert deleted(both) == at
    assert branch not in shown(signed, at)
    query = {"kind": "appendix", "owner": "alice", "name": "labs"}
    assert signed.get("/api/threads", params=query).json() == []
    got = signed.post(f"/review/{crlf['id']}/delete", data={"case": both})
    assert got.status_code == 404
    got = signed.post(f"/review/{crlf['id']}/delete", data={"case": default["case"]})
    assert got.status_code == 404
    elsewhere = {"Sec-Fetch-Site": "cross-site"}
    got = signed.post(
        f"/review/{crlf['id']}/delete", data={"case": alone["case"]}, headers=elsewhere
    )
    assert got.status_code == 403
    assert deleted(alone["case"]) == f"{back}&{urlencode({'case': default['case']})}"
    assert urlencode({"case": alone["case"]}) not in shown(signed, back)


@pytest.mark.slow
def test_a_refusal_s_page_leads_back_where_the_form_was_and_nowhere_else(
    signed: TestClient,
) -> None:
    crlf = family(signed, "crlf")
    back = f"/review/{crlf['id']}?tag=targets"
    form = {"case": "sha256:" + "0" * 64}
    here = {"Referer": f"https://testserver{back}"}
    got = signed.post(f"/review/{crlf['id']}/delete", data=form, headers=here)
    assert got.status_code == 404
    assert f'href="{escape(back)}"' in got.text and "Back to where you were" in got.text
    elsewhere = {"Referer": f"https://elsewhere.example{back}"}
    got = signed.post(f"/review/{crlf['id']}/delete", data=form, headers=elsewhere)
    assert got.status_code == 404 and "Back to where you were" not in got.text
    gone = signed.get("/review/0")
    assert gone.status_code == 404 and "Back to where you were" not in gone.text
    assert ">Home</a>" not in gone.text


@pytest.mark.slow
def test_an_expectation_of_yours_on_another_case_is_offered_to_move_here(
    signed: TestClient,
) -> None:
    crlf = family(signed, "crlf")
    back = f"/review/{crlf['id']}?tag=targets"

    def written(name: str, *under: str) -> tuple[str, str]:
        given = {"name": name, "text": f"{name} found."}
        got = signed.post(f"/api/families/{crlf['id']}/appendices", json=given)
        assert got.status_code == 201
        appendices = {"appendices": [*under, got.json()["head"]["digest"]]}
        got = signed.post(f"/api/families/{crlf['id']}/cases", json=appendices)
        assert got.status_code == 201
        return got.json()["case"], appendices["appendices"][-1]

    alone, ultrasound = written("ultrasound")
    both, _ = written("labs", ultrasound)
    [expected] = signed.get(f"/api/families/{crlf['id']}").json()["cases"][0][
        "expectations"
    ]
    query = {"kind": "expectation", "owner": "alice"}
    [held] = [
        t
        for t in signed.get("/api/threads", params=query).json()
        if t["head"]["digest"] == expected["expectation"]
    ]
    component = {**body(signed, held), "case": alone}
    got = signed.post("/api/threads", json={"component": component, "name": "moved"})
    assert got.status_code == 201
    mine = got.json()

    page = shown(signed, f"{back}&{urlencode({'case': both})}")
    action = f'action="/threads/{mine["id"]}/carry"'
    assert action in page and "Move yours here" in page
    form = page.split(action, 1)[1].split("</form>", 1)[0]
    [head] = re.findall(r'name="head" value="(\d+)"', form)
    assert int(head) == mine["head"]["id"]
    assert "Move yours here" not in shown(
        signed, f"{back}&{urlencode({'case': alone})}"
    )

    got = signed.post(
        f"/threads/{mine['id']}/carry",
        data={"head": head, "case": both, "next": back},
    )
    assert got.status_code == 303
    page = shown(signed, f"{back}&{urlencode({'case': both})}")
    assert "Move yours here" not in page
    assert f'href="/threads/{mine["id"]}#edit"' in page
    assert f'href="/threads/{mine["id"]}#edit"' not in shown(
        signed, f"{back}&{urlencode({'case': alone})}"
    )
