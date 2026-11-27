from typing import Any

import pytest
from fastapi.testclient import TestClient

from chatddx.api.test.helpers import thread
from chatddx.catalog import Entry, EntryField, Subject
from chatddx.identity import Person
from chatddx.store import Catalog
from chatddx.store.store import Connection
from chatddx.test.world import JUDGE, LINES, LINES_GUIDED, LINES_INSTRUCTED, NATIVE, OFF


def configuration(signed: TestClient, owner: str) -> dict[str, Any]:
    query = {"kind": "configuration", "name": LINES, "owner": owner}
    [found] = signed.get("/api/threads", params=query).json()
    return found


@pytest.mark.slow
def test_threads_are_listed_by_kind_among_those_the_person_sees(
    signed: TestClient, conn: Connection, alice: Person
) -> None:
    listed = signed.get("/api/threads", params={"kind": "configuration"}).json()
    assert {t["owner"] for t in listed} == {"alice", "archive"}
    assert {(t["kind"], t["word"]) for t in listed} == {("skeleton", "configuration")}
    assert all(t["title"] and t["head"]["digest"].startswith("sha256:") for t in listed)
    assert configuration(signed, "alice")["language"] == "en"
    for kind, name, language in (
        ("output", "lines", "en"),
        ("sampling", "greedy", None),
    ):
        query = {"kind": kind, "name": name, "owner": "alice"}
        [chunk] = signed.get("/api/threads", params=query).json()
        assert chunk["language"] == language
    named = signed.get("/api/threads", params={"kind": "configuration", "name": LINES})
    assert sorted(t["owner"] for t in named.json()) == ["alice", "archive"]

    mine = configuration(signed, "alice")
    Catalog(conn).note(
        Subject(thread=mine["id"]), Entry(field=EntryField.TAG, value="keep"), alice.id
    )
    kept = signed.get("/api/threads", params={"kind": "configuration", "tag": "keep"})
    assert [t["id"] for t in kept.json()] == [mine["id"]]

    engines = signed.get("/api/threads", params={"kind": "engine"}).json()
    assert engines and {t["kind"] for t in engines} <= {"engine.local", "engine.remote"}
    nope = signed.get("/api/threads", params={"kind": "stack"})
    assert nope.status_code == 422 and nope.json()["detail"].startswith(
        "no kind 'stack'"
    )


@pytest.mark.slow
def test_configurations_are_listed_by_purpose(signed: TestClient) -> None:
    def names(**params: str) -> set[str]:
        query = {"kind": "configuration", **params}
        return {t["name"] for t in signed.get("/api/threads", params=query).json()}

    generation, judges = names(), names(purpose="judge")
    assert names(purpose="generation") == generation
    assert LINES in generation and JUDGE in judges
    assert not generation & judges
    got = signed.get("/api/threads", params={"kind": "scorer", "purpose": "judge"})
    assert got.status_code == 422
    assert got.json()["detail"] == "only a configuration has a purpose"

    answering = names(answers="Answer")
    assert NATIVE in answering and LINES not in answering
    assert answering < generation
    assert names(answers="Verdict", purpose="judge") < judges
    got = signed.get("/api/threads", params={"kind": "scorer", "answers": "Answer"})
    assert (got.status_code, got.json()["detail"]) == (
        422,
        "only a configuration answers",
    )


@pytest.mark.slow
def test_a_thread_is_shown_with_its_recipe_and_its_versions(signed: TestClient) -> None:
    mine, archives = configuration(signed, "alice"), configuration(signed, "archive")

    shown = signed.get(f"/api/threads/{mine['id']}").json()
    assert {k: shown[k] for k in mine} == mine
    assert shown["forked_from"] == archives["head"]["id"]
    assert shown["recipe"]["prompt"].startswith("sha256:")
    assert shown["recipe"]["toolset"] is None
    assert shown["collaborators"] == []

    edits = signed.get(f"/api/threads/{mine['id']}/edits").json()
    assert edits[-1] == {**mine["head"], "version": 1}


def test_a_thread_the_person_doesn_t_see_isn_t_found(
    signed: TestClient, bob: dict[str, str]
) -> None:
    mine = configuration(signed, "alice")
    for path in (f"/api/threads/{mine['id']}", f"/api/threads/{mine['id']}/edits"):
        got = signed.get(path, headers=bob)
        assert got.status_code == 404
        assert got.json() == {
            "detail": f"no thread {mine['id']} for bob",
            "code": "not_found",
        }
    assert (
        signed.get("/api/threads", params={"kind": "configuration"}, headers=bob).json()
        == []
    )


@pytest.mark.slow
def test_a_person_takes_one_expectation_replacing_theirs_only_when_they_say_so(
    signed: TestClient, bob: dict[str, str]
) -> None:
    [found] = signed.get("/api/families", params={"name": "crlf"}).json()
    [held] = signed.get(f"/api/families/{found['id']}").json()["cases"][0][
        "expectations"
    ]
    [archives] = held["shared"]
    taking = f"/api/threads/{archives['id']}/takes"

    got = signed.post(taking, json={})
    assert got.status_code == 409
    assert "already, in thread" in got.json()["detail"]

    got = signed.post(taking, json={"replace": True})
    assert got.status_code == 201
    made = got.json()
    assert got.headers["Location"] == f"/api/threads/{made['id']}"
    assert (made["owner"], made["forked_from"]) == ("alice", archives["head"]["id"])
    [now] = signed.get(f"/api/families/{found['id']}").json()["cases"][0][
        "expectations"
    ]
    assert now["expectation"] == archives["head"]["digest"]
    assert now["ambiguous"] is None

    got = signed.post(f"/api/threads/{made['id']}/takes", json={})
    assert (got.status_code, got.json()) == (
        422,
        {"detail": f"expectation {made['id']} is yours already", "code": "refused"},
    )
    got = signed.post(taking, json={}, headers=bob)
    assert (got.status_code, got.json()) == (
        404,
        {"detail": f"no expectation {archives['id']} for bob", "code": "not_found"},
    )


@pytest.mark.slow
def test_a_lineage_runs_from_the_first_origin_through_every_fork_one_sees(
    signed: TestClient, bob: dict[str, str]
) -> None:
    guided = thread(signed, "configuration", LINES_GUIDED)
    found = signed.get(f"/api/threads/{guided['id']}/lineage").json()
    assert [(k["owner"], k["name"]) for k in found] == [
        ("archive", LINES_INSTRUCTED),
        ("archive", LINES_GUIDED),
        ("alice", LINES_GUIDED),
        ("alice", LINES_INSTRUCTED),
    ]
    first, archives, mine, instructed = found
    assert (first["origin"], first["base"], first["varies"]) == (None, None, [])
    assert (archives["origin"], mine["origin"], instructed["origin"]) == (
        first["id"],
        archives["id"],
        first["id"],
    )
    assert "/recipe/few_shot" in {v["path"] for v in archives["varies"]}
    assert mine["varies"] == [] and mine["base"]["id"] == archives["head"]["id"]
    assert not any(k["behind"] or k["deleted"] for k in found)
    assert signed.get(f"/api/threads/{instructed['id']}/lineage").json() == found

    forked = signed.post(
        f"/api/threads/{instructed['id']}/forks", json={"name": "terse"}
    ).json()
    off = thread(signed, "reasoning", OFF)["head"]["digest"]
    edited = {"head": instructed["head"]["id"], "parts": {"reasoning": off}}
    got = signed.post(f"/api/threads/{instructed['id']}/edits", json=edited)
    assert got.status_code == 201
    assert signed.patch(
        f"/api/threads/{forked['id']}", json={"deleted": True}
    ).is_success
    now = signed.get(f"/api/threads/{guided['id']}/lineage").json()
    [terse] = [k for k in now if k["id"] == forked["id"]]
    assert (terse["origin"], terse["behind"], terse["deleted"]) == (
        instructed["id"],
        True,
        True,
    )
    assert (
        signed.get(f"/api/threads/{guided['id']}/lineage", headers=bob).status_code
        == 404
    )
