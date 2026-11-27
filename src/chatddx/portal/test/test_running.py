import html
import re
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from fastapi.testclient import TestClient

from chatddx import settings
from chatddx.api.test.helpers import digest, thread
from chatddx.inventory import Inventory
from chatddx.portal.test.helpers import (
    compose_props,
    settled,
    shown,
    started,
    world_served,
)
from chatddx.store import Store
from chatddx.store.store import Connection
from chatddx.test.world import LINES, LINES_GUIDED, OFF, faked

__all__ = ["world_served"]


@pytest.mark.slow
def test_a_run_under_way_is_followed_and_halted_on_its_page(
    signed: TestClient, world: Inventory, conn: Connection
) -> None:
    with faked(world, Store(conn).get, delay=0.2):
        run = started(signed)
        page = shown(signed, f"/runs/{run}")
        assert "Reload the page to see how far it has come." in page
        assert 'id="run-live-props"' in page and f'"run": "{run}"' in page
        assert f'action="/runs/{run}/halt"' in page
        assert "Run again" not in page and "Items</h2>" not in page

        got = signed.post(f"/runs/{run}/halt")
        assert (got.status_code, got.headers["location"]) == (303, f"/runs/{run}")
        _ = settled(signed, run)

    page = shown(signed, f"/runs/{run}")
    assert "Items</h2>" in page and 'id="run-live"' not in page
    assert f'action="/runs/{run}/halt"' not in page
    assert f'action="/runs/{run}/scores"' in page and "Left to score:" in page
    assert f'action="/runs/{run}/again"' in page
    left = shown(signed, "/runs?left=true")
    assert f'action="/runs/{run}/scores"' in left

    stale = signed.post(f"/runs/{run}/halt")
    assert (stale.status_code, stale.headers["location"]) == (303, f"/runs/{run}")


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_is_scored_again_and_run_again_from_its_page(signed: TestClient) -> None:
    run = started(signed, score=False)
    _ = settled(signed, run)
    assert "Left to score:" in shown(signed, f"/runs/{run}")

    got = signed.post(f"/runs/{run}/scores")
    assert (got.status_code, got.headers["location"]) == (303, f"/runs/{run}")
    scored = settled(signed, run)
    assert scored["scores"] and "Left to score:" not in shown(signed, f"/runs/{run}")
    stale = signed.post(f"/runs/{run}/scores")
    assert (stale.status_code, stale.headers["location"]) == (303, f"/runs/{run}")
    assert signed.get(f"/api/runs/{run}").json()["job"] == scored["job"]

    got = signed.post(f"/runs/{run}/again")
    assert got.status_code == 303
    again = got.headers["location"].removeprefix("/runs/")
    assert again != run
    shown_again = settled(signed, again)
    assert (shown_again["skeleton"], shown_again["cases"]) == (
        scored["skeleton"],
        scored["cases"],
    )
    assert (
        shown_again["described"].split(" (seed")[0]
        == scored["described"].split(" (seed")[0]
    )


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_links_the_variation_it_ran(signed: TestClient) -> None:
    query = {"kind": "reasoning", "name": OFF, "owner": "alice"}
    [off] = signed.get("/api/threads", params=query).json()
    parts = {"reasoning": off["head"]["digest"]}
    run = started(signed, parts=parts, score=False)
    ran = settled(signed, run)["ran"]
    page = shown(signed, f"/runs/{run}")
    tried = f"/compose/{ran['configuration']}?{urlencode(parts)}"
    assert f'href="{tried}">{LINES}+reasoning={OFF}<' in page


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_the_runs_page_says_how_the_queue_stands_and_pauses_stops_and_resumes_it(
    signed: TestClient,
) -> None:
    page = shown(signed, "/runs")
    assert "0 queued, 0 under way<" in page and 'action="/queue/pause"' in page
    assert 'action="/queue/stop"' not in page

    got = signed.post("/queue/pause")
    assert (got.status_code, got.headers["location"]) == (303, "/runs")
    run = started(signed)
    page = shown(signed, "/runs")
    assert "1 queued, 0 under way, paused" in page
    assert 'action="/queue/resume"' in page and "queued, paused" in page
    assert ">Stop</button>" in page and ">Stop now</button>" not in page

    assert signed.post("/queue/stop").status_code == 303
    page = shown(signed, "/runs")
    assert "stopped: taken out of the queue" in page
    assert 'action="/queue/stop"' not in page
    page = shown(signed, f"/runs/{run}")
    assert f'action="/runs/{run}/resume"' in page and "Run again" in page

    for _ in range(2):
        got = signed.post(f"/runs/{run}/resume")
        assert (got.status_code, got.headers["location"]) == (303, f"/runs/{run}")
    assert signed.post("/queue/resume").status_code == 303
    _ = settled(signed, run)
    done = signed.get(f"/api/runs/{run}").json()
    assert done["finished"] and done["job"]["status"] == "finished"
    page = shown(signed, f"/runs/{run}")
    assert f'action="/runs/{run}/resume"' not in page
    stale = signed.post(f"/runs/{run}/resume")
    assert (stale.status_code, stale.headers["location"]) == (303, f"/runs/{run}")
    assert signed.get(f"/api/runs/{run}").json()["job"] == done["job"]


@pytest.mark.slow
def test_stop_now_halts_the_runs_under_way(
    signed: TestClient, world: Inventory, conn: Connection
) -> None:
    with faked(world, Store(conn).get, delay=0.2):
        run = started(signed)
        page = shown(signed, "/runs")
        for _ in range(500):
            if "1 under way" in page:
                break
            time.sleep(0.02)
            page = shown(signed, "/runs")
        assert ">Stop now</button>" in page and ">Stop</button>" not in page
        got = signed.post("/queue/stop", data={"now": "true"})
        assert got.status_code == 303
        _ = settled(signed, run)
    halted = signed.get(f"/api/runs/{run}").json()
    assert (halted["job"]["status"], halted["job"]["halt"]) == ("stopped", True)
    assert halted["scores"] == []


@pytest.mark.slow
def test_a_form_from_another_site_starts_nothing(signed: TestClient) -> None:
    elsewhere = {"Sec-Fetch-Site": "cross-site"}
    for action in ("halt", "scores", "again", "resume"):
        got = signed.post(
            "/runs/00000000-0000-0000-0000-000000000000/" + action, headers=elsewhere
        )
        assert got.status_code == 403
    for action in ("pause", "resume", "stop"):
        assert signed.post(f"/queue/{action}", headers=elsewhere).status_code == 403


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_whose_scoring_is_queued_is_not_scored_again_by_another_press(
    signed: TestClient,
) -> None:
    first, second = started(signed, score=False), started(signed, score=False)
    for run in (first, second):
        _ = settled(signed, run)
    assert signed.post("/queue/pause").status_code == 303
    assert signed.post(f"/runs/{first}/scores").status_code == 303
    held = signed.get(f"/api/runs/{first}").json()["job"]
    assert held["status"] == "queued"
    left = shown(signed, "/runs?left=true")
    assert f'href="/runs/{first}"' in left
    assert f'action="/runs/{first}/scores"' not in left
    assert f'action="/runs/{second}/scores"' in left
    again = signed.post(f"/runs/{first}/scores")
    assert (again.status_code, again.headers["location"]) == (303, f"/runs/{first}")
    assert signed.get(f"/api/runs/{first}").json()["job"] == held


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_case_is_run_from_its_review_under_each_configuration_that_runs(
    signed: TestClient,
) -> None:
    [crlf] = signed.get("/api/families", params={"name": "crlf"}).json()
    back = f"/review/{crlf['id']}?tag=targets"
    form = {"case": crlf["case"], "back": back}
    got = signed.post(f"/review/{crlf['id']}/runs", data=form)
    assert got.status_code == 303
    location = urlsplit(got.headers["location"])
    query = parse_qs(location.query)
    assert (location.path, location.fragment) == (f"/review/{crlf['id']}", "")
    assert (query["tag"], query["case"]) == (["targets"], [crlf["case"]])
    runs = reaching(signed, crlf)
    by: dict[int, list[dict[str, Any]]] = {}
    for r in runs:
        by.setdefault(r["ran"]["configuration"], []).append(r)
    for held in by.values():
        three, one = sorted(held, key=lambda r: -len(r["seeds"]))
        assert (len(three["seeds"]), len(one["seeds"])) == (3, 1)
        assert three["cases"] == one["cases"] == [crlf["case"]]
        if not three["titled"]["greedy"]:
            assert one["seeds"] == three["seeds"][-1:]
    query = {"kind": "configuration", "purpose": "generation", "owner": "alice"}
    owned = {t["id"] for t in signed.get("/api/threads", params=query).json()}
    assert by and set(by) <= owned
    for r in runs:
        _ = settled(signed, r["id"])

    page = shown(signed, f"{back}&case={crlf['case']}")
    assert 'id="evaluating"' not in page and "review-evaluation" not in page
    elsewhere = {"Sec-Fetch-Site": "cross-site"}
    got = signed.post(f"/review/{crlf['id']}/runs", data=form, headers=elsewhere)
    assert got.status_code == 403


def reaching(signed: TestClient, family: dict[str, Any]) -> list[dict[str, Any]]:
    query = {"reaching": family["case"], "limit": 200}
    return signed.get("/api/runs", params=query).json()


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_case_s_review_runs_no_other_while_one_is_open(signed: TestClient) -> None:
    [crlf] = signed.get("/api/families", params={"name": "crlf"}).json()
    review = f"/review/{crlf['id']}?case={crlf['case']}"
    form = {"case": crlf["case"], "back": review}
    assert '<button class="run">' in shown(signed, review)
    assert signed.post("/queue/pause").status_code == 303
    assert signed.post(f"/review/{crlf['id']}/runs", data=form).status_code == 303
    runs = reaching(signed, crlf)
    assert runs
    assert signed.post(f"/review/{crlf['id']}/runs", data=form).status_code == 303
    assert len(reaching(signed, crlf)) == len(runs)
    assert '<button class="run" disabled>' in shown(signed, review)
    assert signed.post("/queue/resume").status_code == 303
    for r in runs:
        _ = settled(signed, r["id"])
    assert '<button class="run">' in shown(signed, review)


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_review_starts_nothing_over_the_quota(
    signed: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    [crlf] = signed.get("/api/families", params={"name": "crlf"}).json()
    review = f"/review/{crlf['id']}?case={crlf['case']}"
    monkeypatch.setattr(settings, "RUNS_PER_DAY", 1)
    form = {"case": crlf["case"], "back": review}
    got = signed.post(f"/review/{crlf['id']}/runs", data=form)
    assert got.status_code == 429
    assert "over the day's quota" in html.unescape(got.text) or (
        "a day takes 1" in html.unescape(got.text)
    )
    assert signed.get("/api/runs").json() == []


def fared(signed: TestClient, family: dict[str, Any]) -> dict[str, Any]:
    [case] = signed.get(f"/api/families/{family['id']}").json()["cases"]
    [expected] = [e for e in case["expectations"] if e["expectation"]]
    query = {
        "case": family["case"],
        "expectation_schema": expected["expectation_schema"],
    }
    got = signed.get(f"/api/families/{family['id']}/fared", params=query)
    assert got.status_code == 200, got.json()
    return got.json()


def behind(signed: TestClient, family: dict[str, Any]) -> dict[str, list[str]]:
    return {
        c["name"]: [b["why"] for b in c["behind"]]
        for c in fared(signed, family)["configurations"]
    }


def running(signed: TestClient, family: dict[str, Any]) -> None:
    form = {"case": family["case"], "back": f"/review/{family['id']}"}
    assert signed.post(f"/review/{family['id']}/runs", data=form).status_code == 303
    for r in reaching(signed, family):
        _ = settled(signed, r["id"])


def by_configuration(
    signed: TestClient, family: dict[str, Any]
) -> dict[int, list[tuple[str, list[int]]]]:
    found: dict[int, list[tuple[str, list[int]]]] = {}
    for r in reaching(signed, family):
        found.setdefault(r["ran"]["configuration"], []).append((r["id"], r["seeds"]))
    return found


UNRUNNABLE = {"outdated", "untranslated", "refused"}


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_review_s_run_mends_what_the_configuration_or_expectation_changed_since(
    signed: TestClient,
) -> None:
    [crlf] = signed.get("/api/families", params={"name": "crlf"}).json()
    told = behind(signed, crlf)
    assert told[LINES] == ["no_runs"] and fared(signed, crlf)["run"] is True
    running(signed, crlf)
    told = behind(signed, crlf)
    assert all(not why or set(why) <= UNRUNNABLE for why in told.values()), told
    assert told[LINES] == [] and fared(signed, crlf)["run"] is False
    refused = [
        b
        for c in fared(signed, crlf)["configurations"]
        for b in c["behind"]
        if b["why"] == "refused"
    ]
    assert refused and all(b["refusal"]["detail"] for b in refused)
    before = by_configuration(signed, crlf)
    running(signed, crlf)
    assert by_configuration(signed, crlf) == before

    off = digest(signed, "reasoning", OFF)
    lines = thread(signed, "configuration", LINES)
    edited = {"head": lines["head"]["id"], "parts": {"reasoning": off}}
    got = signed.post(f"/api/threads/{lines['id']}/edits", json=edited)
    assert got.status_code == 201
    assert behind(signed, crlf)[LINES] == ["changed"]
    running(signed, crlf)
    after = by_configuration(signed, crlf)
    assert after.keys() == before.keys()
    for c, runs in after.items():
        if c == lines["id"]:
            fresh = [r for r in runs if r not in before[c]]
            assert sorted(s for _, s in fresh) == sorted(s for _, s in before[c])
        else:
            assert runs == before[c]
    assert behind(signed, crlf)[LINES] == []

    [case] = signed.get(f"/api/families/{crlf['id']}").json()["cases"]
    [expected] = [e for e in case["expectations"] if e["expectation"]]
    query = {"kind": "expectation", "owner": "alice"}
    [mine] = [
        t
        for t in signed.get("/api/threads", params=query).json()
        if t["head"]["digest"] == expected["expectation"]
    ]
    held = signed.get(f"/api/components/{mine['head']['digest']}").json()["body"]
    worded = {**held["data"]["warning"], "text": "Bleeding on anticoagulants."}
    changed = {**held, "data": {**held["data"], "warning": worded}}
    got = signed.post(
        f"/api/threads/{mine['id']}/edits",
        json={"head": mine["head"]["id"], "component": changed},
    )
    assert got.status_code == 201
    assert behind(signed, crlf)[LINES] == []

    warning = {**worded, "pattern": worded["pattern"] + " | apixaban"}
    changed = {**held, "data": {**held["data"], "warning": warning}}
    got = signed.post(
        f"/api/threads/{mine['id']}/edits",
        json={"head": got.json()["id"], "component": changed},
    )
    assert got.status_code == 201
    told = behind(signed, crlf)
    unscored = {c for c, why in told.items() if why == ["unscored"]}
    assert unscored and LINES not in unscored
    before = by_configuration(signed, crlf)
    running(signed, crlf)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and any(
        why == ["unscored"] for why in behind(signed, crlf).values()
    ):
        time.sleep(0.2)
    assert all(why != ["unscored"] for why in behind(signed, crlf).values())
    assert by_configuration(signed, crlf) == before


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_review_s_run_runs_again_on_the_same_seeds_what_was_halted(
    signed: TestClient,
) -> None:
    [crlf] = signed.get("/api/families", params={"name": "crlf"}).json()
    assert signed.post("/queue/pause").status_code == 303
    form = {"case": crlf["case"], "back": f"/review/{crlf['id']}"}
    assert signed.post(f"/review/{crlf['id']}/runs", data=form).status_code == 303
    assert behind(signed, crlf)[LINES] == ["under_way"]
    assert fared(signed, crlf)["run"] is False
    for r in reaching(signed, crlf):
        assert signed.post(f"/runs/{r['id']}/halt").status_code == 303
    assert signed.post("/queue/resume").status_code == 303
    assert behind(signed, crlf)[LINES] == ["halted"]
    before = by_configuration(signed, crlf)
    running(signed, crlf)
    after = by_configuration(signed, crlf)
    for c, runs in after.items():
        fresh = [r for r in runs if r not in before[c]]
        assert sorted(s for _, s in fresh) == sorted(s for _, s in before[c])
    assert behind(signed, crlf)[LINES] == []


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_configuration_s_baseline_is_run_from_compose(signed: TestClient) -> None:
    query = {"kind": "configuration", "purpose": "generation", "owner": "alice"}
    mine = min(
        signed.get("/api/threads", params=query).json(),
        key=lambda t: t["name"] or t["title"],
    )
    compose = f"/compose/{mine['id']}"
    assert based(signed, compose) == NO_RUNS
    got = signed.post(f"{compose}/runs")
    assert (got.status_code, got.headers["location"]) == (303, compose)
    runs = [
        r
        for r in signed.get("/api/runs", params={"limit": 200}).json()
        if r["ran"]["configuration"] == mine["id"]
    ]
    targets = signed.get("/api/families", params={"tag": "targets"}).json()
    sent = {c for r in runs for c in r["cases"]}
    assert sent and sent <= {f["case"] for f in targets}
    assert set(compose_props(shown(signed, compose))["baseline"]["runs"]) == {
        r["id"] for r in runs
    }
    assert {len(r["seeds"]) for r in runs} == {1}
    assert len(runs) == 2 * len({tuple(r["cases"]) for r in runs})
    for r in runs:
        _ = settled(signed, r["id"])
    assert based(signed, compose) == WHOLE
    assert signed.post(f"{compose}/runs").status_code == 303
    again = [
        r
        for r in signed.get("/api/runs", params={"limit": 200}).json()
        if r["ran"]["configuration"] == mine["id"]
    ]
    fresh = [r for r in again if r["id"] not in {r["id"] for r in runs}]
    assert len(fresh) == len(runs)
    assert {s for r in fresh for s in r["seeds"]}.isdisjoint(
        {s for r in runs for s in r["seeds"]}
    ) or all(r["titled"]["greedy"] for r in runs)

    for r in fresh:
        _ = settled(signed, r["id"])
    got = signed.get(f"/api/threads/{mine['id']}/breakdown")
    assert got.status_code == 200, got.json()
    broken = got.json()
    assert broken["tag"] == "targets" and broken["views"]
    gatherings = broken["gatherings"]
    assert [g["point"]["version"] for g in gatherings] == [1, 1]
    assert [g["point"]["missing"] for g in gatherings] == [0, 0]
    for g in gatherings:
        assert len(g["estimates"]) == len(g["values"]) == len(broken["views"])
    assert gatherings[0]["paired"] == [None] * len(broken["views"])
    assert any(d is not None for d in gatherings[1]["paired"])

    first, second = (g["point"]["started"] for g in gatherings)
    got = signed.get(f"/api/gatherings/{second}")
    assert got.status_code == 200, got.json()
    held = got.json()
    assert held["configuration"] == mine["id"] and held["gathering"] == gatherings[1]
    assert held["before"]["point"]["started"] == first
    assert {r["run"] for r in held["runs"]} == {r["id"] for r in fresh}
    assert sorted(r["repeat"] for r in held["runs"]) == [False, True] * (
        len(fresh) // 2
    )
    assert [r["case"] for r in held["rows"]] == sorted(sent)
    for row in held["rows"]:
        assert row["answered"] and row["alike"] is not None
        assert len(row["replicate"]) == len(row["repeat"]) == len(broken["views"])
        assert any(v is not None for v in row["replicate"])
        assert any(v is not None for v in row["before"])
    page = html.unescape(shown(signed, f"/gatherings/{second}"))
    assert f"/gatherings/{first}" in page
    scored = re.findall(r'href="(/scores/[^"]+)"', page)
    assert scored and all(signed.get(u).status_code == 200 for u in set(scored))
    assert all(f"/runs/{r['id']}" in page for r in fresh)
    unknown = "00000000-0000-0000-0000-000000000000"
    assert signed.get(f"/api/gatherings/{unknown}").status_code == 404


@pytest.mark.usefixtures("fake")
def test_a_baseline_with_a_case_it_has_no_translation_for_runs_nothing(
    signed: TestClient,
) -> None:
    [svenska] = signed.get("/api/families", params={"name": "svenska"}).json()
    tagged = {"tags": [*svenska["tags"], "targets"]}
    assert (
        signed.patch(f"/api/families/{svenska['id']}", json=tagged).status_code == 200
    )
    lines = thread(signed, "configuration", LINES)
    compose = f"/compose/{lines['id']}"
    assert based(signed, compose) == {"running": False, "behind": False, "whole": False}
    assert "No translation into" in html.unescape(shown(signed, compose))

    assert signed.post(f"{compose}/runs").status_code == 303
    assert signed.get("/api/runs", params={"limit": 200}).json() == []


@pytest.mark.usefixtures("fake")
def test_a_baseline_with_texts_left_to_translate_runs_nothing_and_says_nothing_above(
    signed: TestClient,
) -> None:
    [svenska] = signed.get("/api/families", params={"name": "svenska"}).json()
    tagged = {"tags": [*svenska["tags"], "targets"]}
    assert (
        signed.patch(f"/api/families/{svenska['id']}", json=tagged).status_code == 200
    )
    guided = thread(signed, "configuration", LINES_GUIDED)
    compose = f"/compose/{guided['id']}"
    assert based(signed, compose) == NO_RUNS

    drafted = compose_props(shown(signed, compose))["drafted"]
    into = {k: dict(list(v.items())[1:]) for k, v in drafted["into"].items()}
    saved = {"head": guided["head"]["id"], "chunks": drafted["chunks"]}
    got = signed.post(
        f"/api/threads/{guided['id']}/saves", json={**saved, "translations": into}
    )
    assert got.status_code == 201, got.json()
    assert based(signed, compose) == {"running": False, "behind": False, "whole": False}
    page = html.unescape(shown(signed, compose))
    assert "No translation into" not in page and "can't be done" not in page

    assert signed.post(f"{compose}/runs").status_code == 303
    assert signed.get("/api/runs", params={"limit": 200}).json() == []


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_review_and_a_baseline_over_the_same_case_stand_apart(
    signed: TestClient,
) -> None:
    [crlf] = signed.get("/api/families", params={"name": "crlf"}).json()
    assert "targets" in crlf["tags"]
    running(signed, crlf)
    query = {"kind": "configuration", "purpose": "generation", "owner": "alice"}
    mine = min(
        signed.get("/api/threads", params=query).json(),
        key=lambda t: t["name"] or t["title"],
    )
    compose = f"/compose/{mine['id']}"
    assert based(signed, compose) == NO_RUNS
    assert signed.post(f"{compose}/runs").status_code == 303
    for r in signed.get("/api/runs", params={"limit": 200}).json():
        _ = settled(signed, r["id"])
    assert based(signed, compose) == WHOLE
    assert "not_whole" not in behind(signed, crlf)[mine["name"] or mine["title"]]
    running(signed, crlf)
    assert based(signed, compose) == WHOLE


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_baseline_falls_behind_as_an_expectation_changes_and_is_scored_again(
    signed: TestClient,
) -> None:
    [crlf] = signed.get("/api/families", params={"name": "crlf"}).json()
    lines = thread(signed, "configuration", LINES)
    compose = f"/compose/{lines['id']}"
    assert signed.post(f"{compose}/runs").status_code == 303
    for r in signed.get("/api/runs", params={"limit": 200}).json():
        _ = settled(signed, r["id"])
    assert based(signed, compose) == WHOLE
    runs = signed.get("/api/runs", params={"limit": 200}).json()

    [case] = signed.get(f"/api/families/{crlf['id']}").json()["cases"]
    [expected] = [e for e in case["expectations"] if e["expectation"]]
    query = {"kind": "expectation", "owner": "alice"}
    [mine] = [
        t
        for t in signed.get("/api/threads", params=query).json()
        if t["head"]["digest"] == expected["expectation"]
    ]
    held = signed.get(f"/api/components/{mine['head']['digest']}").json()["body"]
    diagnosis = {**held["data"]["diagnosis"]}
    diagnosis["pattern"] = diagnosis["pattern"] + " | apixaban"
    changed = {**held, "data": {**held["data"], "diagnosis": diagnosis}}
    got = signed.post(
        f"/api/threads/{mine['id']}/edits",
        json={"head": mine["head"]["id"], "component": changed},
    )
    assert got.status_code == 201
    assert based(signed, compose) == BEHIND

    assert signed.post(f"{compose}/runs").status_code == 303
    again = signed.get("/api/runs", params={"limit": 200}).json()
    assert {r["id"] for r in again} == {r["id"] for r in runs}
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and based(signed, compose) != WHOLE:
        time.sleep(0.2)
    assert based(signed, compose) == WHOLE


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_an_earlier_version_s_baseline_is_run_from_compose(signed: TestClient) -> None:
    lines = thread(signed, "configuration", LINES)
    first = lines["head"]["id"]
    off = digest(signed, "reasoning", OFF)
    edited = {"head": first, "parts": {"reasoning": off}}
    assert (
        signed.post(f"/api/threads/{lines['id']}/edits", json=edited).status_code == 201
    )
    compose = f"/compose/{lines['id']}"
    got = signed.post(f"{compose}/runs", data={"head": str(first)})
    assert (got.status_code, got.headers["location"]) == (
        303,
        f"{compose}?head={first}",
    )
    runs = signed.get("/api/runs", params={"limit": 200}).json()
    assert runs and {r["ran"]["head"] for r in runs} == {first}
    for r in runs:
        _ = settled(signed, r["id"])
    assert based(signed, f"{compose}?head={first}") == WHOLE
    assert based(signed, compose) == NO_RUNS


NO_RUNS = BEHIND = {"running": False, "behind": True, "whole": False}
WHOLE = {"running": False, "behind": False, "whole": True}


def based(signed: TestClient, compose: str) -> dict[str, bool]:
    held = compose_props(shown(signed, compose))["baseline"]
    return {k: v for k, v in held.items() if k != "runs"}
