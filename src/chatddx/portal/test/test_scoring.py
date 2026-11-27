import json
import re
from statistics import mean
from typing import Any

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

from chatddx.api.test.helpers import family, thread
from chatddx.portal.test.helpers import (
    ran_template,
    run_title,
    said,
    shown,
    submitted,
)
from chatddx.test.world import LINES, NATIVE

__all__ = ["ran_template"]


def props(page: str) -> dict[str, Any]:
    held = page.split('<script type="application/json" id="scoring-props">', 1)[1]
    return json.loads(held.split("</script>", 1)[0])


def shown_mean(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


@pytest.mark.slow
def test_scoring_leads_to_a_scorer_beside_every_scorer_and_judge(
    signed: TestClient,
) -> None:
    got = signed.get("/scoring")
    scorers = signed.get("/api/threads", params={"kind": "scorer"}).json()
    judges = signed.get("/api/threads", params={"kind": "judge"}).json()
    assert got.status_code == 303
    assert got.headers["location"] in {f"/scoring/{t['id']}" for t in scorers}
    page = shown(signed, got.headers["location"])
    for t in [*scorers, *judges]:
        assert f'href="/scoring/{t["id"]}"' in page
    assert 'href="/scoring"' in shown(signed, "/runs")
    lines = thread(signed, "configuration", LINES)
    assert signed.get(f"/scoring/{lines['id']}").status_code == 404


@pytest.mark.slow
def test_a_scorer_names_its_judges_what_it_reads_and_how_its_runs_scored(
    signed: TestClient,
) -> None:
    judged = thread(signed, "scorer", "judged", "archive")
    digest = judged["head"]["digest"]
    page = shown(signed, f"/scoring/{judged['id']}")
    text = said(page)

    held = signed.get(f"/api/components/{digest}").json()["body"]
    for v in held["views"]:
        assert escape(v["expectation"]) in page
    for name in ("verdict", "graded"):
        judge = thread(signed, "judge", name, "archive")
        assert f'href="/scoring/{judge["id"]}"' in page

    reads = text.split("Configurations read", 1)[1].split("Configurations left out", 1)[
        0
    ]
    skips = text.split("Configurations left out", 1)[1].split("Expected", 1)[0]
    assert LINES in [n.strip() for n in reads.split(",")]
    assert NATIVE in [n.strip() for n in skips.split(",")]
    families = signed.get("/api/families").json()
    assert f"of the {len(families)} cases you see" in text

    runs = signed.get("/api/runs", params={"scored_by": digest}).json()
    assert runs
    for r in runs:
        [graded] = [
            g
            for g in signed.get(f"/api/runs/{r['id']}/scores").json()
            if g["scorer"] == digest
        ]
        means = " ".join(shown_mean(m) for m in graded["means"])
        assert f'href="/runs/{r["id"]}"' in page
        assert re.search(
            re.escape(run_title(r)) + r" \S+ \S+ " + re.escape(means), text
        )


@pytest.mark.slow
def test_a_judge_shows_who_asks_it_what_it_is_asked_and_where_its_seeds_disagree(
    signed: TestClient,
) -> None:
    graded = thread(signed, "judge", "graded", "archive")
    judged = thread(signed, "scorer", "judged", "archive")
    page = shown(signed, f"/scoring/{graded['id']}")
    text = said(page)

    body = signed.get(f"/api/components/{graded['head']['digest']}").json()["body"]
    configurations = signed.get(
        "/api/threads", params={"kind": "configuration", "purpose": "judge"}
    ).json()
    asks = [t for t in configurations if t["head"]["digest"] == body["skeleton"]]
    assert asks and any(f'href="/compose/{t["id"]}"' in page for t in asks)
    assert f'href="/scoring/{judged["id"]}"' in page
    assert re.search(r"archive/judged · note-graded latest version", text)
    assert "‹completion›" in text

    held = signed.get(f"/api/components/{judged['head']['digest']}").json()["body"]
    [at] = [
        i
        for i, v in enumerate(held["views"])
        if v.get("judge") == graded["head"]["digest"]
    ]
    items: list[list[float | None]] = []
    values: list[float] = []
    runs = signed.get("/api/runs", params={"scored_by": judged["head"]["digest"]})
    for r in runs.json():
        [score] = [
            g["score"]
            for g in signed.get(f"/api/runs/{r['id']}/scores").json()
            if g["scorer"] == judged["head"]["digest"]
        ]
        for i in signed.get(f"/api/runs/{r['id']}/scores/{score}/items").json()[
            "items"
        ]:
            if i["view"] == at and i["judge_calls"]:
                items.append(i["detail"]["seeds"])
                values += [] if i["value"] is None else [i["value"]]
    agree = sum(len(set(s)) == 1 and None not in s for s in items)
    short = sum(None in s for s in items)
    assert re.search(
        rf"judged · note-graded {len(items)} {agree} {short} {shown_mean(mean(values))}",
        text,
    )
    disagreeing = [s for s in items if len({v for v in s if v is not None}) > 1]
    assert disagreeing
    for seeds in disagreeing:
        assert " ".join(shown_mean(v) for v in seeds) in text


@pytest.mark.slow
def test_a_judge_is_read_with_a_view_asking_it_and_what_a_case_expects(
    signed: TestClient,
) -> None:
    verdict = thread(signed, "judge", "verdict", "archive")
    judged = thread(signed, "scorer", "judged", "archive")
    noted = family(signed, "noted")
    crlf = family(signed)
    page = shown(signed, f"/scoring/{verdict['id']}")
    held = signed.get(f"/api/components/{judged['head']['digest']}").json()["body"]
    [first, _] = [
        i
        for i, v in enumerate(held["views"])
        if v.get("judge") == verdict["head"]["digest"]
    ]
    [case] = signed.get(f"/api/families/{noted['id']}").json()["cases"]
    [expected] = case["expectations"]
    [carol] = [n for n in expected["data"]["notes"] if n["author"] == "carol"]

    assert submitted(page, f"/scoring/{verdict['id']}") == {
        "view": [f"{judged['id']}.{first}"],
        "family": [str(noted["id"])],
    }
    assert escape(carol["comment"]) in page
    given = props(page)
    assert given["expectation"] == held["views"][first]["expectation"]
    assert given["data"] == expected["data"] and given["me"] == "alice"
    assert given["judge"]["thread"] == verdict["id"]
    assert given["judge"]["head"] == verdict["head"]["id"]
    assert given["judge"]["texts"]["parts"]["prompt"] is not None

    page = shown(signed, f"/scoring/{verdict['id']}?family={crlf['id']}")
    assert escape(carol["comment"]) not in page and "‹expectation›" in page
    assert props(page)["data"] != expected["data"]
    page = shown(signed, f"/scoring/{verdict['id']}?family=0")
    assert escape(carol["comment"]) in page
    assert signed.get(f"/scoring/{verdict['id']}?view=0.0").status_code == 404


@pytest.mark.slow
def test_a_judge_is_offered_to_change_with_the_texts_it_is_asked_through(
    signed: TestClient,
) -> None:
    held = thread(signed, "judge", "verdict", "archive")
    verdict = props(shown(signed, f"/scoring/{held['id']}"))["judge"]
    body = signed.get(f"/api/components/{held['head']['digest']}").json()["body"]
    assert (verdict["thread"], verdict["head"]) == (held["id"], held["head"]["id"])
    assert verdict["body"] == body
    texts = verdict["texts"]
    asked = texts["configuration"]
    query = {"kind": "configuration", "purpose": "judge"}
    judging = {t["id"]: t for t in signed.get("/api/threads", params=query).json()}
    assert judging[asked["thread"]]["head"]["digest"] == body["skeleton"]
    assert asked["head"] == judging[asked["thread"]]["head"]["id"]
    for part in ("instructions", "prompt", "output"):
        digest = texts["recipe"][part]
        chunk = texts["parts"][part]
        if digest is None:
            assert chunk is None
            continue
        found = signed.get(f"/api/components/{digest}").json()
        assert (chunk["digest"], chunk["body"]) == (digest, found["body"])
    assert texts["parts"]["prompt"]["thread"] is not None


@pytest.mark.slow
def test_a_scorer_follows_a_judge_s_latest_version_from_the_judge_s_page(
    signed: TestClient,
) -> None:
    archives = thread(signed, "judge", "verdict", "archive")
    judged = thread(signed, "scorer", "judged", "archive")
    body = signed.get(f"/api/components/{archives['head']['digest']}").json()["body"]
    fork = {"name": "verdict", "component": {**body, "seeds": [2]}}
    assert signed.post(f"/api/threads/{archives['id']}/forks", json=fork).is_success
    mine = thread(signed, "judge", "verdict")
    page = shown(signed, f"/scoring/{mine['id']}")
    assert (
        "archive/judged · note-comment archive/verdict, which it is forked from"
        in said(page)
    )
    action = f"/scoring/{mine['id']}/follow"
    given = submitted(page, action)
    assert given == {"scorer": [str(judged["id"])], "head": [str(judged["head"]["id"])]}
    got = signed.post(action, data=given)
    assert (got.status_code, got.headers["location"]) == (303, f"/scoring/{mine['id']}")

    def views(t: dict[str, Any]) -> list[dict[str, Any]]:
        held = signed.get(f"/api/components/{t['head']['digest']}").json()["body"]
        return held["views"]

    def labels(t: dict[str, Any]) -> Any:
        return signed.get(f"/api/threads/{t['id']}/edits").json()[-1]["labels"]

    ours = thread(signed, "scorer", "judged")
    was = views(judged)
    assert [v.get("judge") for v in views(ours)] == [
        mine["head"]["digest"]
        if v.get("judge") == archives["head"]["digest"]
        else v.get("judge")
        for v in was
    ]
    assert labels(ours) == labels(judged) and labels(ours)["views"]
    assert thread(signed, "scorer", "judged", "archive")["head"] == judged["head"]

    edit = {"head": mine["head"]["id"], "component": {**body, "seeds": [3]}}
    assert signed.post(f"/api/threads/{mine['id']}/edits", json=edit).is_success
    mine = thread(signed, "judge", "verdict")
    page = shown(signed, f"/scoring/{mine['id']}")
    assert "alice/judged · note-comment version 1 of 2" not in said(page)
    assert "judged · note-comment version 1 of 2" in said(page)
    assert submitted(page, action) == {
        "scorer": [str(ours["id"]), str(judged["id"])],
        "head": [str(ours["head"]["id"]), str(judged["head"]["id"])],
    }
    assert ">Ask its latest version</button>" in page
    given = {"scorer": str(ours["id"]), "head": str(ours["head"]["id"])}
    assert signed.post(action, data=given).status_code == 303
    followed = thread(signed, "scorer", "judged")
    assert followed["head"]["id"] != ours["head"]["id"]
    assert sum(v.get("judge") == mine["head"]["digest"] for v in views(followed)) == 2
    assert labels(followed) == labels(judged)
    assert signed.post(f"/scoring/{judged['id']}/follow", data=given).status_code == 404


@pytest.mark.slow
def test_a_scorer_and_a_judge_are_led_to_from_the_library(
    signed: TestClient,
) -> None:
    judged = thread(signed, "scorer", "judged", "archive")
    verdict = thread(signed, "judge", "verdict", "archive")
    for t in (judged, verdict):
        assert f'href="/scoring/{t["id"]}"' in shown(signed, f"/threads/{t['id']}")
