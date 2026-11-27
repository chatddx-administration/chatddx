from typing import Any

import pytest
from fastapi.testclient import TestClient

from chatddx.api.test.helpers import body, endpoint, thread
from chatddx.test.world import CLINICIAN, JUDGE, LINES, QWEN, QWEN_ARTIFACT


@pytest.mark.slow
def test_a_component_is_written_as_a_thread_of_one_s_own(signed: TestClient) -> None:
    archives = thread(signed, "instructions", CLINICIAN, "archive")
    held = body(signed, archives)
    asked = {
        "component": {**held, "text": "You are a careful physician."},
        "name": "careful",
        "language": "en",
    }

    got = signed.post("/api/threads", json=asked)
    assert got.status_code == 201
    made = got.json()
    assert got.headers["location"] == f"/api/threads/{made['id']}"
    assert (made["kind"], made["name"], made["owner"], made["language"]) == (
        "chunk.instructions",
        "careful",
        "alice",
        "en",
    )
    assert (made["forked_from"], made["findings"]) == (None, [])

    edits = f"/api/threads/{made['id']}/edits"
    terse = {"head": made["head"]["id"], "component": {**held, "text": "Be terse."}}
    got = signed.post(edits, json=terse)
    assert got.status_code == 201
    edited = got.json()
    assert signed.post(edits, json={**terse, "head": edited["id"]}).status_code == 200
    moved = signed.post(edits, json={**terse, "component": held})
    assert moved.status_code == 409

    fork = {"name": "svensk", "component": {**held, "text": "Var noggrann."}}
    got = signed.post(
        f"/api/threads/{archives['id']}/forks", json={**fork, "language": "sv"}
    )
    assert got.status_code == 201
    forked = got.json()
    assert (forked["forked_from"], forked["language"]) == (
        archives["head"]["id"],
        "sv",
    )


@pytest.mark.slow
def test_a_write_is_refused_what_isn_t_the_person_s(
    signed: TestClient, bob: dict[str, str]
) -> None:
    archives = thread(signed, "instructions", CLINICIAN, "archive")
    mine = thread(signed, "configuration", LINES)
    held = body(signed, archives)
    sampling = body(signed, thread(signed, "sampling", "greedy", "archive"))
    forks = f"/api/threads/{archives['id']}/forks"
    head = archives["head"]["id"]
    refusals: list[tuple[str, dict[str, Any], int, str]] = [
        (
            "/api/threads",
            {"component": {"kind": "tool"}, "name": "x"},
            422,
            "isn't a kind",
        ),
        (
            "/api/threads",
            {"component": sampling, "name": "x", "language": "en"},
            422,
            "chunk.sampling components have no language of their own",
        ),
        (
            "/api/threads",
            {"component": {**held, "text": 7}, "name": "x"},
            422,
            "validation error",
        ),
        (forks, {"name": "x", "parts": {"prompt": None}}, 422, "only a configuration"),
        (
            f"/api/threads/{mine['id']}/forks",
            {"name": "x", "component": held},
            422,
            "a configuration is written with parts, not a component",
        ),
        (
            f"/api/threads/{archives['id']}/edits",
            {"head": head},
            422,
            "an edit holds a component",
        ),
        (
            f"/api/threads/{archives['id']}/edits",
            {"head": head, "component": held},
            404,
            f"no instructions {archives['id']} of yours",
        ),
    ]
    for path, asked, status, said in refusals:
        got = signed.post(path, json=asked)
        assert got.status_code == status, (path, asked, got.json())
        assert said in got.json()["detail"]

    got = signed.post(forks, json={"name": "bob's"}, headers=bob)
    assert (got.status_code, got.json()) == (
        404,
        {"detail": f"no instructions {archives['id']} for bob", "code": "not_found"},
    )


@pytest.mark.slow
def test_an_expectation_s_edit_says_what_the_lints_say(signed: TestClient) -> None:
    [family] = signed.get("/api/families", params={"name": "crlf"}).json()
    [expected] = signed.get(f"/api/families/{family['id']}").json()["cases"][0][
        "expectations"
    ]
    threads = signed.get(
        "/api/threads", params={"kind": "expectation", "owner": "alice"}
    )
    [mine] = [
        t for t in threads.json() if t["head"]["digest"] == expected["expectation"]
    ]
    held = body(signed, mine)
    got = signed.post(
        f"/api/threads/{mine['id']}/edits",
        json={"head": mine["head"]["id"], "component": {**held, "data": [1]}},
    )
    assert got.status_code == 201
    assert [f["code"] for f in got.json()["findings"]] == ["expectation.invalid"]

    got = signed.post(
        "/api/threads", json={"component": {**held, "data": [2]}, "name": "again"}
    )
    assert got.status_code == 422
    assert f"already, in thread {mine['id']}" in got.json()["detail"]

    data = held["data"]
    broken = {**data, "diagnosis": {**data["diagnosis"], "pattern": "copd | (asthma"}}
    component = {**held, "data": broken}
    got = signed.post("/api/components/check", json=component)
    assert got.status_code == 200
    [found] = [
        f for f in got.json()["findings"] if f["code"] == "expectation.unreadable"
    ]
    assert (found["message"], found["params"]["field"]) == (
        "a '(' in 'copd | (asthma' is never closed",
        "diagnosis",
    )
    got = signed.post(
        f"/api/threads/{mine['id']}/edits",
        json={"head": got_head(signed, mine), "component": component},
    )
    assert (got.status_code, got.json()["detail"]) == (
        422,
        "a '(' in 'copd | (asthma' is never closed",
    )


def got_head(signed: TestClient, thread: dict[str, Any]) -> int:
    return signed.get(f"/api/threads/{thread['id']}").json()["head"]["id"]


@pytest.mark.slow
def test_an_expectation_alone_goes_unnamed(signed: TestClient) -> None:
    [family] = signed.get("/api/families", params={"name": "crlf"}).json()
    [expected] = signed.get(f"/api/families/{family['id']}").json()["cases"][0][
        "expectations"
    ]
    threads = signed.get(
        "/api/threads", params={"kind": "expectation", "owner": "alice"}
    )
    [mine] = [
        t for t in threads.json() if t["head"]["digest"] == expected["expectation"]
    ]
    held = body(signed, mine)
    gone = signed.patch(f"/api/threads/{mine['id']}", json={"deleted": True})
    assert gone.status_code == 200
    got = signed.post("/api/threads", json={"component": held})
    assert got.status_code == 201, got.json()
    made = signed.get(f"/api/threads/{got.json()['id']}").json()
    assert made["name"] is None and made["expecting"] is not None

    instructions = body(signed, thread(signed, "instructions", CLINICIAN, "archive"))
    got = signed.post("/api/threads", json={"component": instructions})
    assert got.status_code == 422
    assert "only an expectation goes unnamed" in got.json()["detail"]


@pytest.mark.slow
def test_a_recipe_of_one_s_making_is_a_new_configuration(signed: TestClient) -> None:
    def digest(kind: str, name: str) -> str:
        return thread(signed, kind, name, "archive")["head"]["digest"]

    recipe = {
        "instructions": digest("instructions", CLINICIAN),
        "prompt": digest("prompt", "case"),
        "output": digest("output", "native"),
        "sampling": digest("sampling", "greedy"),
        "model": endpoint(signed, QWEN)["serves"],
    }
    listed = signed.get("/api/threads", params={"kind": "configuration"}).json()
    got = signed.post("/api/threads", json={"recipe": recipe, "name": "my own"})
    assert got.status_code == 201
    made = got.json()
    assert made["head"]["digest"] not in {t["head"]["digest"] for t in listed}
    assert (made["kind"], made["owner"], made["forked_from"]) == (
        "skeleton",
        "alice",
        None,
    )
    assert {k: made["recipe"][k] for k in recipe} == recipe
    assert made["language"] == "en" and made["findings"] == []

    held = body(signed, thread(signed, "instructions", CLINICIAN, "archive"))
    for asked, said in (
        ({"recipe": recipe, "component": held}, "a component or a recipe, not both"),
        ({}, "a component or a recipe, not both"),
        ({"recipe": {**recipe, "prompt": recipe["output"]}}, "isn't a stored chunk"),
        ({"recipe": recipe, "language": "en"}, "comes from its recipe"),
        ({"recipe": {**recipe, "stack": "x"}}, "validation error"),
    ):
        got = signed.post("/api/threads", json={**asked, "name": "x"})
        assert got.status_code == 422, (asked, got.json())
        assert said in str(got.json()["detail"])


@pytest.mark.slow
def test_a_judge_is_written_over_a_judge_configuration(signed: TestClient) -> None:
    query = {"kind": "configuration", "purpose": "judge", "name": JUDGE}
    [judging] = signed.get("/api/threads", params={**query, "owner": "alice"}).json()
    judge = {
        "kind": "judge",
        "skeleton": judging["head"]["digest"],
        "model": thread(signed, "model", QWEN_ARTIFACT, "archive")["head"]["digest"],
        "seeds": [1, 2],
    }
    got = signed.post("/api/threads", json={"component": judge, "name": "twice"})
    assert got.status_code == 201
    made = got.json()
    assert (made["kind"], made["owner"]) == ("judge", "alice")
    assert [f["code"] for f in made["findings"]] == ["judge.greedy_seeds"]

    generation = thread(signed, "configuration", LINES)["head"]["digest"]
    wrong = {**judge, "skeleton": generation}
    got = signed.post("/api/threads", json={"component": wrong, "name": "wrong"})
    assert got.status_code == 422
    assert "judge uses a generation skeleton" in got.json()["detail"]
