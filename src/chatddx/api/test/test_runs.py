import json
import time
from contextlib import suppress
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from chatddx import settings
from chatddx.api import telling
from chatddx.api.app import app
from chatddx.api.test.helpers import (
    UNDER_WAY,
    Told,
    asked,
    digest,
    endpoint,
    family,
    followed,
    joined,
    listened,
    names,
    sent,
    thread,
    told,
    world_served,
)
from chatddx.bench import Bench
from chatddx.bench.test.helpers import ran, trial
from chatddx.catalog import Entry, EntryField, Subject
from chatddx.curation import Plan
from chatddx.factors.base import Finding, resolve
from chatddx.factors.trial import Trial
from chatddx.identity import Person
from chatddx.inventory import Inventory
from chatddx.scripted.test.helpers import held
from chatddx.store import Catalog, People, Queue, Store
from chatddx.store.store import Connection
from chatddx.test.world import (
    COMPARED,
    GPT_OSS,
    JUDGE,
    LINES,
    LINES_GUIDED,
    NATIVE_TOOLS,
    OFF,
    QWEN,
    QWEN_ARTIFACT,
    faked,
)

__all__ = ["world_served"]


def engine(signed: TestClient, name: str) -> str:
    return endpoint(signed, name)["engine"]


def model(signed: TestClient, name: str) -> str:
    return endpoint(signed, name)["serves"]


def rows(said: Told) -> Told:
    return [s for s in said if s[0] is not None]


def finished(signed: TestClient, run: str) -> dict[str, Any]:
    for _ in range(500):
        shown = signed.get(f"/api/runs/{run}").json()
        if shown["finished"] and shown["scores"]:
            return shown
        time.sleep(0.02)
    raise AssertionError(f"run {run} wasn't finished and scored")


@pytest.mark.slow
def test_a_run_is_accepted_and_told_by_its_events(
    signed: TestClient, world: Inventory, conn: Connection
) -> None:
    case = family(signed, "crlf")["case"]
    with faked(world, Store(conn).get, delay=UNDER_WAY):
        got = signed.post("/api/runs", json=asked(signed))
        assert got.status_code == 202
        [started] = got.json()["runs"]
        assert got.json()["left_out"] == []
        said = followed(signed, started["run"])
    assert got.headers["location"] == f"/api/runs/{started['run']}"
    assert (started["endpoint"], started["cases"]) == (QWEN, [case])
    assert (started["seeds"], started["greedy"]) == ([7], False)

    ids = [i for i, _, _ in rows(said) if i is not None]
    assert ids == sorted(set(ids))
    assert said[0][1:] == ("run.started", started) and said[0][0] is not None
    assert names(said)[-2:] == ["run.scored", "done"]
    assert said[-1][2] == {"halted": False}
    expected = {"item.started", "item.ended", "run.finished", "run.scoring"}
    assert expected | {"score.started", "score.item"} <= set(names(said))
    [ended] = [d for _, n, d in said if n == "item.ended"]
    assert (ended["case"], ended["outcome"], ended["why"]) == (case, "completed", None)

    made = signed.get(got.headers["location"]).json()
    assert (made["endpoint"], made["cases"], made["seeds"]) == (QWEN, [case], [7])
    assert made["finished"] and made["finished_at"] is not None
    assert made["rig"]["distribution"] == "chatddx"
    [item] = made["items"]
    assert (item["case"], item["replicate"], item["outcome"]) == (case, 0, "completed")
    assert item["completion_tokens"] > 0
    [scored] = [d for _, n, d in said if n == "run.scored"]
    assert scored["scores"] == made["scores"]
    graded = {g["name"]: g for g in made["scores"]}
    lines = graded["lines"]
    assert lines["score"] is not None and lines["refused"] is None
    assert lines["labels"] == ["text", "differential", "dont-miss"]
    assert {(s["case"], s["view"]) for s in lines["items"]} == {
        (case, view) for view in range(3)
    }
    [scoring] = [d for _, n, d in said if n == "run.scoring"]
    assert {s["name"] for s in scoring["scorers"]} == set(graded)


@pytest.mark.slow
def test_a_run_s_events_stream_as_they_come_and_then_the_ledger_tells_them(
    signed: TestClient,
    world: Inventory,
    conn: Connection,
    alice: Person,
    listening: str,
) -> None:
    queue = Queue(conn)
    queue.pause(alice.id)
    bearer = {"Authorization": signed.headers["Authorization"]}
    with (
        faked(world, Store(conn).get, delay=UNDER_WAY),
        httpx2.Client(headers=bearer) as http,
    ):
        run = signed.post("/api/runs", json=asked(signed, score=False)).json()["runs"][
            0
        ]["run"]
        said = joined(http, listening, run, lambda: queue.pause(alice.id, False))
    content = [d for _, n, d in said if n == "item.delta" and d["kind"] == "content"]
    assert "".join(d["text"] for d in content).strip()
    assert content[-1]["tokens"] > 0
    assert names(said)[-2:] == ["run.finished", "done"]

    again = followed(signed, run)
    assert rows(again) == rows(said)
    assert [s[1:] for s in again[:-1]] == [
        s[1:] for s in said if s[1] not in {"item.delta", "done"}
    ]
    assert again[-1] == (None, "done", {"halted": False})
    [(ended, _, _)] = [s for s in again if s[1] == "item.ended"]
    assert ended is not None
    assert followed(signed, run, **{"Last-Event-ID": str(ended)}) == [
        s for s in again if s[1] in {"run.finished", "done"}
    ]
    last = rows(again)[-1][0]
    past = followed(signed, run, **{"Last-Event-ID": str(last)})
    assert past == [again[-1]]


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_is_told_alike_by_its_rows_in_another_process(
    signed: TestClient, db: str, world: Inventory
) -> None:
    made, said = sent(signed, asked(signed))
    elsewhere = app(world, make_conninfo(settings.database(), dbname=db))
    with TestClient(elsewhere, base_url="https://testserver") as other:
        other.headers.update(signed.headers)
        recorded = followed(other, made["id"])
    assert rows(recorded) == rows(said)
    assert {"score.started", "score.item"} <= {n for _, n, _ in rows(recorded)}
    assert recorded[-2][1:] == ("run.scored", {"scores": made["scores"]})
    assert recorded[-1][1:] == ("done", {"halted": False})


def test_a_run_told_from_the_ledger_tells_what_it_noted(
    signed: TestClient, conn: Connection, alice: Person, plan: Plan
) -> None:
    noted = Finding(code="case.drift", message="the vignette moved", subject="x")
    run = ran(conn, alice, trial(conn, plan, LINES, "crlf"), findings=[noted])
    said = followed(signed, str(run))
    assert names(said)[-3:] == ["run.noted", "run.finished", "done"]
    assert said[-3][2]["code"] == "case.drift"


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_is_a_job_in_the_queue_until_it_is_scored(
    signed: TestClient, conn: Connection, alice: Person
) -> None:
    made, _ = sent(signed, asked(signed, concurrency=2))
    queue, run = Queue(conn), UUID(made["id"])
    placed = queue.placed([run]).get(run)
    assert placed is not None and queue.open(run) is None
    job = placed.job
    assert (job.owner, job.endpoint, job.slots) == (alice.id, QWEN, 2)
    assert (job.score, job.scorers, job.status, job.halt) == (
        True,
        None,
        "finished",
        False,
    )
    got = signed.post(f"/api/runs/{uuid4()}/halt")
    assert got.status_code == 404


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_of_tags_runs_the_case_of_each_family_tagged(signed: TestClient) -> None:
    tagged = signed.get("/api/families", params={"tag": "targets"}).json()
    body = {**asked(signed), "families": None, "tags": ["targets"], "score": False}
    made, said = sent(signed, body)
    assert sorted(i["case"] for i in made["items"]) == sorted(f["case"] for f in tagged)
    assert made["scores"] == [] and "run.scoring" not in names(said)


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_start_is_a_run_per_language_and_leaves_out_what_it_can_t_send(
    signed: TestClient,
) -> None:
    tagged = signed.get("/api/families", params={"tag": "swedish"}).json()
    language = {f["case"]: f["language"] for f in tagged}
    swedish = sorted(case for case, said in language.items() if said == "sv")
    body = {"families": None, "tags": ["swedish"], "score": False}
    got = signed.post("/api/runs", json={**asked(signed, LINES_GUIDED), **body})
    assert got.status_code == 202, got.json()
    first, translated = got.json()["runs"]
    assert got.json()["left_out"] == []
    assert got.headers["location"] == f"/api/runs/{first['run']}"
    assert (first["language"], translated["language"]) == ("en", "sv")
    assert first["cases"] == [c for c in language if language[c] == "en"]
    assert sorted(translated["cases"]) == swedish
    for run in (first, translated):
        assert names(followed(signed, run["run"]))[-1] == "done"
    listed = signed.get("/api/runs", params={"with": first["run"]}).json()
    assert {(r["id"], r["language"], r["started_with"]) for r in listed} == {
        (first["run"], "en", None),
        (translated["run"], "sv", first["run"]),
    }

    plain = signed.post("/api/runs", json={**asked(signed), **body}).json()
    [run] = plain["runs"]
    assert run["cases"] == first["cases"]
    assert [
        (o["language"], sorted(o["cases"]), o["why"]) for o in plain["left_out"]
    ] == [("sv", swedish, "lines has no translation into sv")]
    _ = followed(signed, run["run"])
    alone = [f["id"] for f in tagged if f["language"] == "sv"][:1]
    got = signed.post("/api/runs", json={**asked(signed), "families": alone})
    assert got.status_code == 422
    assert got.json()["detail"] == ("lines has no translation into sv")


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_the_gate_refuses_is_unprocessable_and_isn_t_recorded(
    signed: TestClient,
) -> None:
    for body, said in (
        (
            asked(signed, NATIVE_TOOLS),
            "the configuration's tools would get content from source test",
        ),
        (
            asked(signed, parts={"model": model(signed, GPT_OSS)}),
            f"endpoint '{GPT_OSS}' can't be",
        ),
    ):
        got = signed.post("/api/runs", json=body)
        assert got.status_code == 422
        assert said in got.json()["detail"]
    assert signed.get("/api/runs").json() == []


@pytest.mark.slow
def test_a_run_the_request_names_wrong_is_unprocessable(signed: TestClient) -> None:
    good = asked(signed)
    chunk = thread(signed, "reasoning", OFF)
    query = {"kind": "configuration", "purpose": "judge", "name": JUDGE}
    judge = signed.get("/api/threads", params={**query, "owner": "alice"}).json()[0]
    wrong: list[tuple[dict[str, Any], str]] = [
        ({"tags": ["swedish"]}, "a run takes one of families, tags or cases"),
        ({"families": None}, "a run takes one of families, tags or cases"),
        ({"families": []}, "at least 1 item"),
        ({"families": None, "cases": []}, "at least 1 item"),
        ({"families": [999]}, "no case 999 for alice"),
        ({"families": None, "tags": ["nowhere"]}, "no case tagged nowhere for alice"),
        ({"under": "nowhere"}, "runs under its model's handle: set its model instead"),
        ({"parts": {"model": None}}, "a configuration always holds its model"),
        ({"configuration": chunk["id"]}, f"no configuration {chunk['id']} for alice"),
        ({"parts": {"prompt": chunk["head"]["digest"]}}, "isn't a stored chunk"),
        ({"configuration": judge["id"]}, "judge is a judge configuration"),
        ({"replicates": 2}, "a run takes seeds or replicates, not both"),
        ({"seeds": []}, "at least 1 item"),
        ({"cleanup": ["tidy@1"]}, "newlines.lf@1"),
    ]
    for changed, said in wrong:
        got = signed.post("/api/runs", json={**good, **changed})
        assert got.status_code == 422, changed
        assert said in json.dumps(got.json()["detail"])
    assert signed.get("/api/runs").json() == []


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_runs_are_listed_newest_first_and_filtered(signed: TestClient) -> None:
    off = digest(signed, "reasoning", OFF)
    first, _ = sent(signed, asked(signed))
    second, _ = sent(
        signed, asked(signed, seeds=[8], parts={"reasoning": off}, score=False)
    )
    assert second["scores"] == []
    scorer = thread(signed, "scorer", "lines", "archive")["head"]["digest"]

    def listed(**params: Any) -> list[str]:
        return [r["id"] for r in signed.get("/api/runs", params=params).json()]

    assert listed() == [second["id"], first["id"]]
    assert listed(limit=1) == [second["id"]]
    assert listed(offset=1) == [first["id"]]
    assert listed(trial=first["trial"]) == [first["id"]]
    assert listed(reaching=second["skeleton"]) == [second["id"]]
    assert listed(reaching=first["cases"][0]) == [second["id"], first["id"]]
    assert listed(scored_by=scorer) == [first["id"]]
    [shown] = signed.get("/api/runs", params={"limit": 1, "offset": 1}).json()
    assert shown == {k: first[k] for k in shown}
    assert signed.get("/api/runs", params={"limit": 0}).status_code == 422


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_no_browser_keeps_what_is_sensitive(signed: TestClient) -> None:
    made, _ = sent(signed, asked(signed))
    run, [score, *_] = made["id"], made["scores"]
    kept = {
        path: signed.get(path).headers.get("cache-control")
        for path in (
            f"/api/runs/{run}",
            f"/api/runs/{run}/items",
            f"/api/runs/{run}/events",
            f"/api/runs/{run}/scores",
            f"/api/runs/{run}/scores/{score['score']}/items",
            f"/api/families/{family(signed, 'crlf')['id']}/vignette",
        )
    }
    assert [path for path, said in kept.items() if said == "no-store"] == [
        f"/api/runs/{run}/items",
        f"/api/runs/{run}/events",
        f"/api/runs/{run}/scores/{score['score']}/items",
        f"/api/families/{family(signed, 'crlf')['id']}/vignette",
    ]


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_s_items_hold_its_calls_and_render_again_as_they_were_sent(
    signed: TestClient,
) -> None:
    made, _ = sent(signed, asked(signed, score=False))
    [item] = signed.get(f"/api/runs/{made['id']}/items").json()
    assert {k: item[k] for k in made["items"][0]} == made["items"][0]
    assert item["why"] is None and item["turns"] == []
    assert item["call"]["response"]["choices"]
    said = item["call"]["response"]["choices"][0]["message"]["content"]
    assert item["answer"] == {"value": said, "problem": None, "salvaged": False}
    assert item["vignette"]["hex"]

    [again] = signed.get(f"/api/runs/{made['id']}/rendered-again").json()
    assert again == {
        "case": item["case"],
        "replicate": 0,
        "same": True,
        "why": None,
    }


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_another_s_run_isn_t_found(signed: TestClient, bob: dict[str, str]) -> None:
    made, _ = sent(signed, asked(signed, score=False))
    for path in ("", "/items", "/rendered-again", "/events"):
        got = signed.get(f"/api/runs/{made['id']}{path}", headers=bob)
        assert (got.status_code, got.json()) == (
            404,
            {"detail": f"no run {made['id']} of yours", "code": "not_found"},
        )
    got = signed.post(f"/api/runs/{made['id']}/halt", headers=bob)
    assert got.status_code == 404
    assert signed.get("/api/runs", headers=bob).json() == []
    assert signed.get("/api/runs/not-a-run").status_code == 422


def test_the_events_are_described(described: dict[str, Any]) -> None:
    paths = described["paths"]
    assert "202" in paths["/api/runs"]["post"]["responses"]
    told = paths["/api/runs/{run}/events"]["get"]["responses"]["200"]
    assert set(told["content"]) == {"text/event-stream"}
    assert "`run.started`" in told["description"] and "`done`" in told["description"]
    schemas = described["components"]["schemas"]
    expected = {"RunStartedData", "ItemDeltaData", "RunScoredData", "DoneData"}
    assert expected | {"ScoreStartedData", "JudgeAnsweredData"} <= set(schemas)


@pytest.mark.slow
def test_a_halt_stops_a_run_which_is_finished_and_left_to_score(
    signed: TestClient, listening: str, world: Inventory, conn: Connection
) -> None:
    alice = {"Authorization": signed.headers["Authorization"]}
    with (
        faked(world, Store(conn).get, delay=0.1),
        httpx2.Client(headers=alice) as http,
    ):
        run = signed.post("/api/runs", json=asked(signed)).json()["runs"][0]["run"]
        with http.stream(
            "GET", f"{listening}/api/runs/{run}/events", timeout=10
        ) as got:
            lines = got.iter_lines()
            for line in lines:
                if line == "event: item.delta":
                    break
            assert signed.post(f"/api/runs/{run}/halt").status_code == 204
            rest = "\n".join(lines)
    said = told(rest[rest.index("id: ") :])
    assert names(said)[-2:] == ["run.finished", "done"]
    assert said[-1][2] == {"halted": True}
    shown = signed.get(f"/api/runs/{run}").json()
    [item] = shown["items"]
    assert (item["outcome"], shown["finished"], shown["scores"]) == (
        "stopped",
        True,
        [],
    )
    got = signed.post(f"/api/runs/{run}/halt")
    assert (got.status_code, got.json()) == (
        409,
        {
            "detail": f"run {run} has nothing under way",
            "code": "conflict",
            "wording": "run %(run)s has nothing under way",
            "params": {"run": str(run)},
        },
    )


@pytest.mark.slow
def test_a_run_whose_listener_goes_away_goes_on(
    signed: TestClient, listening: str, world: Inventory, conn: Connection
) -> None:
    alice = {"Authorization": signed.headers["Authorization"]}
    with (
        faked(world, Store(conn).get, delay=0.005),
        httpx2.Client(headers=alice) as http,
    ):
        run = signed.post("/api/runs", json=asked(signed)).json()["runs"][0]["run"]
        with http.stream(
            "GET", f"{listening}/api/runs/{run}/events", timeout=10
        ) as got:
            for line in got.iter_lines():
                if line == "event: item.delta":
                    break
        shown = finished(signed, run)
    [item] = shown["items"]
    assert item["outcome"] == "completed"


@pytest.mark.slow
def test_a_stopping_server_cuts_a_run_s_events_off_after_its_grace(
    served: FastAPI,
    signed: TestClient,
    world: Inventory,
    conn: Connection,
    alice: Person,
) -> None:
    Queue(conn).pause(alice.id)
    with faked(world, Store(conn).get):
        run = signed.post("/api/runs", json=asked(signed)).json()["runs"][0]["run"]
    bearer = {"Authorization": signed.headers["Authorization"]}
    with listened(served) as (url, server), httpx2.Client(headers=bearer) as http:
        with http.stream("GET", f"{url}/api/runs/{run}/events", timeout=30) as got:
            lines = got.iter_lines()
            assert next(lines) == "id: 1"
            server.should_exit = True
            stopped = time.monotonic()
            with suppress(httpx2.RemoteProtocolError):
                for _ in lines:
                    pass
        assert time.monotonic() - stopped < settings.SERVE_GRACE.total_seconds() + 2


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_is_named_by_its_variation_and_runs_the_edit_given(
    signed: TestClient,
) -> None:
    off = digest(signed, "reasoning", OFF)
    mine = thread(signed, "configuration", LINES)
    first = mine["head"]
    ran: dict[str, Any] = {
        "configuration": mine["id"],
        "head": first["id"],
        "parts": {},
    }
    varied, _ = sent(signed, asked(signed, parts={"reasoning": off}, score=False))
    assert varied["described"].startswith(
        f"{LINES}+reasoning={OFF} × {QWEN_ARTIFACT} × "
    )
    assert varied["ran"] == {**ran, "parts": {"reasoning": off}}
    plain, _ = sent(signed, asked(signed, score=False))
    assert plain["described"].startswith(f"{LINES} × {QWEN_ARTIFACT} × ")
    assert plain["ran"] == ran

    edits = f"/api/threads/{mine['id']}/edits"
    later = signed.post(edits, json={"head": first["id"], "parts": {"reasoning": off}})
    assert later.status_code == 201
    earlier, _ = sent(signed, asked(signed, head=first["id"], score=False))
    assert earlier["skeleton"] == first["digest"] != later.json()["digest"]
    assert earlier["ran"] == ran
    got = signed.post("/api/runs", json=asked(signed, head=10**9))
    assert (got.status_code, got.json()) == (
        422,
        {
            "detail": f"no edit {10**9} of configuration {mine['id']}",
            "code": "refused",
        },
    )


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_runs_are_held_to_a_day_s_quota_and_a_run_to_its_items(
    signed: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ITEMS_PER_RUN", 0)
    got = signed.post("/api/runs", json=asked(signed))
    assert (got.status_code, got.json()["detail"], got.json()["code"]) == (
        429,
        "a run holds at most 0 items, not 1",
        "over_quota",
    )
    monkeypatch.setattr(settings, "ITEMS_PER_RUN", 1)
    monkeypatch.setattr(settings, "RUNS_PER_DAY", 1)
    first = signed.post("/api/runs", json=asked(signed))
    assert first.status_code == 202
    _ = finished(signed, first.json()["runs"][0]["run"])
    got = signed.post("/api/runs", json=asked(signed))
    assert (got.status_code, got.json()["detail"], got.json()["code"]) == (
        429,
        "over the day's quota: 2 of 1",
        "over_quota",
    )
    assert len(signed.get("/api/runs").json()) == 1


@pytest.mark.slow
def test_a_quiet_stream_is_kept_alive(
    signed: TestClient,
    listening: str,
    world: Inventory,
    conn: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(telling, "KEEP_ALIVE", 0.02)
    alice = {"Authorization": signed.headers["Authorization"]}
    with (
        faked(world, Store(conn).get, delay=0.2),
        httpx2.Client(headers=alice) as http,
    ):
        run = signed.post("/api/runs", json=asked(signed)).json()["runs"][0]["run"]
        with http.stream(
            "GET", f"{listening}/api/runs/{run}/events", timeout=10
        ) as got:
            for line in got.iter_lines():
                if line == ": keep-alive":
                    break
            assert signed.post(f"/api/runs/{run}/halt").status_code == 204


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_takes_replicates_cleanup_a_concurrency_and_an_order(
    signed: TestClient, conn: Connection
) -> None:
    body = asked(
        signed,
        seeds=None,
        replicates=2,
        cleanup=["strip@1"],
        concurrency=2,
        order="replicate_major@1",
        score=False,
    )
    shown, said = sent(signed, body)
    [started] = [data for _, name, data in said if name == "run.started"]
    assert len(shown["seeds"]) == 2 and started["seeds"] == shown["seeds"]
    stored = Store(conn).run(UUID(shown["id"])).started
    assert resolve(Store(conn).get, stored.trial, Trial).cleanup == ("strip@1",)
    execution = stored.execution
    assert (execution.concurrency, execution.order) == (2, "replicate_major@1")

    again = signed.post(f"/api/runs/{shown['id']}/again", json={"score": False})
    assert again.status_code == 202
    assert len(again.json()["seeds"]) == 2
    _ = followed(signed, again.json()["run"])
    got = signed.post("/api/runs", json={**body, "concurrency": 5})
    assert got.status_code == 422
    assert "takes 4 at once" in got.json()["detail"]


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_runs_again_with_another_seed_under_its_name(
    signed: TestClient, bob: dict[str, str]
) -> None:
    off = digest(signed, "reasoning", OFF)
    first, _ = sent(signed, asked(signed, parts={"reasoning": off}, score=False))
    got = signed.post(f"/api/runs/{first['id']}/again", json={"seeds": [9]})
    assert got.status_code == 202
    started = got.json()
    assert got.headers["location"] == f"/api/runs/{started['run']}"
    assert started["run"] != first["id"]
    assert (started["skeleton"], started["cases"], started["seeds"]) == (
        first["skeleton"],
        first["cases"],
        [9],
    )
    _ = followed(signed, started["run"])
    again = signed.get(got.headers["location"]).json()
    assert (again["endpoint"], again["seeds"]) == (first["endpoint"], [9])
    assert again["described"] == first["described"].replace("(seed 7)", "(seed 9)")
    assert again["ran"] == first["ran"] is not None

    got = signed.post(f"/api/runs/{first['id']}/again", json={}, headers=bob)
    assert (got.status_code, got.json()["code"]) == (404, "not_found")


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_doesn_t_run_again_on_a_case_its_owner_no_longer_sees(
    signed: TestClient, conn: Connection, alice: Person
) -> None:
    first, _ = sent(signed, asked(signed, score=False))
    crlf = family(signed, "crlf")
    archive = People(conn).find("archive")
    assert archive is not None
    unshared = Entry(field=EntryField.COLLABORATOR, person=alice.id, present=False)
    Catalog(conn).note(Subject(family=crlf["id"]), unshared, archive.id)
    got = signed.post(f"/api/runs/{first['id']}/again", json={})
    assert (got.status_code, got.json()["code"]) == (422, "refused")
    assert got.json()["detail"] == f"no case {crlf['case']} for alice"


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_s_items_and_a_score_s_are_read_for_one_case(signed: TestClient) -> None:
    both = [family(signed, name) for name in ("crlf", "bom")]
    made, _ = sent(signed, asked(signed, families=[f["id"] for f in both]))
    run, [score, *_] = made["id"], made["scores"]
    for f in both:
        case = {"case": f["case"]}
        items = signed.get(f"/api/runs/{run}/items", params=case).json()
        assert [i["case"] for i in items] == [f["case"]]
        path = f"/api/runs/{run}/scores/{score['score']}/items"
        scored = signed.get(path, params=case).json()["items"]
        assert scored and {i["case"] for i in scored} == {f["case"]}
    assert len(signed.get(f"/api/runs/{run}/items").json()) == 2


@pytest.mark.slow
@pytest.mark.parametrize("template", ["ran"], indirect=True)
def test_runs_are_compared_over_the_items_they_share(
    signed: TestClient, bench: Bench
) -> None:
    runs = [str(held(bench, name).run) for name in COMPARED]
    got = signed.get("/api/runs/compared", params={"run": runs})
    assert got.status_code == 200
    compared = got.json()
    assert [r["id"] for r in compared["runs"]] == runs
    views = {(v["name"], v["label"]): v for v in compared["views"]}
    differential = views[(LINES, "differential")]
    assert differential["means"] == [0.75, 0.5, 0.0]
    items = [(i["case"], i["replicate"]) for i in compared["items"]]
    cases = compared["runs"][0]["cases"]
    assert items == [(case, 0) for case in cases]
    by_item = list(zip(*differential["values"]))
    assert sorted(by_item) == [(0.5, 1.0, 0.0), (1.0, 0.0, 0.0)]
    assert views[(LINES, "dont-miss")]["values"] == [[None, None]] * 3
    assert compared["apart"] == []

    appendix = str(held(bench, "appendix").run)
    apart = signed.get("/api/runs/compared", params={"run": [runs[0], appendix]}).json()
    assert apart["items"] == []
    assert {c["case"]: c["runs"] for c in apart["apart"]} == {
        **{case: [runs[0]] for case in cases},
        apart["runs"][1]["cases"][0]: [appendix],
    }
    assert all(v["values"] == [[], []] for v in apart["views"])

    assert signed.get("/api/runs/compared").status_code == 422
    unknown = signed.get("/api/runs/compared", params={"run": [str(uuid4())]})
    assert unknown.status_code == 404
