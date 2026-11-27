from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from chatddx.api.schemas import Parts
from chatddx.api.test.helpers import digest, endpoint, sign_in, thread
from chatddx.bench import Bench
from chatddx.bench.test.helpers import another_expectation
from chatddx.curation import load_cases
from chatddx.factors.request import RECIPE_PARTS, Translations
from chatddx.store import Store
from chatddx.store.store import Connection
from chatddx.test.world import (
    DATA,
    GPT_OSS,
    GPT_OSS_ARTIFACT,
    JUDGE,
    LINES,
    LINES_GUIDED,
    NATIVE,
    NATIVE_TOOLS,
    OFF,
    QWEN,
)

DIFFERENTIAL = ("answer", "differential")


def variation(
    signed: TestClient, configuration: dict[str, Any], **params: Any
) -> dict[str, Any]:
    got = signed.get(f"/api/threads/{configuration['id']}/variation", params=params)
    assert got.status_code == 200, got.json()
    return got.json()


def parts(shown: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["part"]: p for p in shown["parts"]}


def test_a_request_names_the_recipe_s_parts(described: dict[str, Any]) -> None:
    assert tuple(Parts.model_fields) == RECIPE_PARTS
    get = described["paths"]["/api/threads/{thread}/variation"]["get"]
    assert {p["name"] for p in get["parameters"]} == {
        "thread",
        *RECIPE_PARTS,
        "head",
        "under",
        "tag",
        "seed",
    }


@pytest.mark.slow
def test_a_configuration_with_nothing_replaced_is_itself(signed: TestClient) -> None:
    mine = thread(signed, "configuration", LINES)
    shown = variation(signed, mine, seed=7)
    assert (shown["head"], shown["skeleton"]) == (mine["head"], mine["head"]["digest"])
    assert not shown["greedy"]

    held = parts(shown)
    recipe = signed.get(f"/api/threads/{mine['id']}").json()["recipe"]
    assert {p: held[p]["digest"] for p in RECIPE_PARTS} == {
        p: recipe[p] for p in RECIPE_PARTS
    }
    assert not any(p["replaced"] for p in held.values())
    assert (held["output"]["title"], held["output"]["summary"]) == (
        "lines",
        "text output",
    )
    assert held["reasoning"] == {
        "part": "reasoning",
        "digest": None,
        "title": None,
        "summary": None,
        "replaced": False,
        "landed": None,
        "nearest": [],
    }
    assert (held["sampling"]["landed"], held["sampling"]["nearest"]) == ("on", [])

    request = shown["request"]
    served = endpoint(signed, QWEN)["engine"]
    assert (request["model"], request["seed"]) == (served, 7)
    assert "‹vignette›‹appendices›" in str(request["messages"])
    assert shown["findings"] == []
    english, swedish = shown["languages"]
    assert (english["language"], english["translated"], english["refused"]) == (
        "en",
        False,
        None,
    )
    assert english["skeleton"] == shown["skeleton"]
    assert (swedish["language"], len(swedish["families"]), swedish["skeleton"]) == (
        "sv",
        3,
        None,
    )
    assert (swedish["refused"], swedish["untranslated"]) == (
        "lines has no translation into sv",
        True,
    )


@pytest.mark.slow
def test_a_variation_replaces_parts_by_digest_or_takes_them_out(
    signed: TestClient,
) -> None:
    mine = thread(signed, "configuration", LINES)
    off = digest(signed, "reasoning", OFF)
    shown = variation(signed, mine, reasoning=off)
    assert shown["head"] == mine["head"]
    assert shown["skeleton"] != mine["head"]["digest"]
    reasoning = parts(shown)["reasoning"]
    assert (reasoning["digest"], reasoning["title"], reasoning["replaced"]) == (
        off,
        OFF,
        True,
    )
    assert (reasoning["summary"], reasoning["landed"]) == ("reasoning off", "off")
    assert shown["request"]["chat_template_kwargs"] == {"enable_thinking": False}

    gpt_oss = endpoint(signed, GPT_OSS)["serves"]
    swapped = variation(signed, mine, reasoning=off, model=gpt_oss)
    held = parts(swapped)
    assert (held["model"]["digest"], held["model"]["replaced"]) == (gpt_oss, True)
    assert (held["reasoning"]["landed"], held["sampling"]["landed"]) == ("low", "low")
    assert "always reasons" in held["reasoning"]["nearest"][0]
    request = swapped["request"]
    served = endpoint(signed, GPT_OSS)["engine"]
    assert (request["model"], request["reasoning_effort"]) == (served, "low")

    own = parts(shown)["prompt"]["digest"]
    same = variation(signed, mine, prompt=own)
    assert same["skeleton"] == mine["head"]["digest"]
    assert not parts(same)["prompt"]["replaced"]

    web = thread(signed, "configuration", NATIVE_TOOLS)
    assert "tools" in variation(signed, web)["request"]
    taken = variation(signed, web, toolset="")
    toolset = parts(taken)["toolset"]
    assert (toolset["digest"], toolset["replaced"]) == (None, True)
    assert "tools" not in taken["request"]


@pytest.mark.slow
def test_a_variation_is_labelled_and_says_which_configuration_holds_it(
    signed: TestClient,
) -> None:
    mine = thread(signed, "configuration", LINES)
    archives = thread(signed, "configuration", LINES, "archive")
    assert mine["head"]["digest"] == archives["head"]["digest"]
    for looked in (mine, archives):
        shown = variation(signed, looked)
        assert shown["label"] == LINES
        assert shown["held_by"] == mine

    off = digest(signed, "reasoning", OFF)
    shown = variation(signed, archives, reasoning=off)
    assert shown["label"] == f"{LINES}+reasoning={OFF}"
    assert shown["held_by"] is None
    forks = f"/api/threads/{archives['id']}/forks"
    made = signed.post(forks, json={"name": "terse", "parts": {"reasoning": off}})
    held = variation(signed, archives, reasoning=off)["held_by"]
    assert held is not None
    assert (held["id"], held["name"]) == (made.json()["id"], "terse")


@pytest.mark.slow
def test_a_variation_of_an_earlier_edit_is_looked_at_and_forked(
    signed: TestClient,
) -> None:
    mine = thread(signed, "configuration", LINES)
    first = mine["head"]
    off = digest(signed, "reasoning", OFF)
    edits = f"/api/threads/{mine['id']}/edits"
    now = signed.post(edits, json={"head": first["id"], "parts": {"reasoning": off}})
    later = now.json()

    shown = variation(signed, mine, head=first["id"])
    assert (shown["head"], shown["skeleton"]) == (first, first["digest"])
    assert parts(shown)["reasoning"]["digest"] is None
    assert variation(signed, mine, head=later["id"])["skeleton"] == later["digest"]
    assert variation(signed, mine)["head"]["id"] == later["id"]
    varied = variation(signed, mine, head=first["id"], reasoning=off)
    assert varied["skeleton"] == later["digest"]

    forks = f"/api/threads/{mine['id']}/forks"
    got = signed.post(forks, json={"name": "before", "head": first["id"]})
    assert got.status_code == 201
    made = got.json()
    assert (made["forked_from"], made["head"]["digest"]) == (
        first["id"],
        first["digest"],
    )

    archives = thread(signed, "configuration", LINES, "archive")
    path = f"/api/threads/{mine['id']}/variation"
    for edit in (archives["head"]["id"], 10**9):
        got = signed.get(path, params={"head": edit})
        assert (got.status_code, got.json()) == (
            404,
            {
                "detail": f"no edit {edit} of configuration {mine['id']}",
                "code": "not_found",
            },
        )
        got = signed.post(forks, json={"name": "nowhere", "head": edit})
        assert got.status_code == 404

    chunk = thread(signed, "reasoning", OFF)
    got = signed.post(
        f"/api/threads/{chunk['id']}/forks",
        json={"name": "x", "head": chunk["head"]["id"]},
    )
    assert (got.status_code, got.json()["detail"]) == (
        422,
        "only a configuration is forked from an edit: another kind from a component",
    )


@pytest.mark.slow
def test_the_seed_is_drawn_unless_given_and_greedy_sampling_sends_none(
    signed: TestClient,
) -> None:
    mine = thread(signed, "configuration", LINES)
    drawn = variation(signed, mine)
    assert 0 <= drawn["seed"] < 2**31
    assert drawn["request"]["seed"] == drawn["seed"]

    greedy = variation(signed, mine, sampling=digest(signed, "sampling", "greedy"))
    assert greedy["greedy"]
    assert "seed" not in greedy["request"]


@pytest.mark.slow
def test_a_variation_is_rendered_and_linted_for_the_engine_serving_its_model(
    signed: TestClient,
) -> None:
    web = thread(signed, "configuration", NATIVE_TOOLS)
    engine = endpoint(signed, QWEN)["engine"]
    shown = variation(signed, web)
    assert shown["request"]["model"] == engine
    codes = {f["code"] for f in shown["findings"]}
    assert "vllm.native_tools_uncallable" in codes
    assert [c["language"] for c in shown["languages"] if c["untranslated"]] == ["sv"]
    assert variation(signed, web, seed=shown["seed"]) == shown

    english = variation(signed, web, tag="targets")
    assert "translations.missing" not in {f["code"] for f in english["findings"]}
    assert [c["language"] for c in english["languages"]] == ["en"]
    tagged = signed.get("/api/families", params={"tag": "targets"}).json()
    assert {f["language"] for f in tagged} == {"en"}
    assert {r["cases"] for r in english["reach"]} == {len(tagged)}

    nowhere = variation(signed, web, tag="nowhere")
    assert {r["cases"] for r in nowhere["reach"]} == {0}
    assert [f["code"] for f in nowhere["findings"]] == ["vllm.native_tools_uncallable"]
    assert nowhere["languages"] == []


@pytest.mark.slow
def test_each_scorer_view_s_reach_names_the_families_it_misses(
    signed: TestClient,
) -> None:
    listed = signed.get("/api/families").json()
    families = sorted(f["id"] for f in listed)
    native = variation(signed, thread(signed, "configuration", NATIVE))
    reach = {(r["name"], r["label"]): r for r in native["reach"]}
    differential = reach[DIFFERENTIAL]
    assert differential["scorer"] == thread(signed, "scorer", "answer", "archive")["id"]
    assert (differential["offered"], differential["cases"]) == (True, len(families))
    assert differential["missing"] == []
    dont_miss = {
        id
        for id, case in load_cases(DATA).items()
        if isinstance(case.targets, dict) and "dont_miss" in case.targets
    }
    assert dont_miss
    assert sorted(reach["answer", "dont-miss"]["missing"]) == sorted(
        f["id"] for f in listed if f["name"] not in dont_miss
    )

    lines = variation(signed, thread(signed, "configuration", LINES))
    reach = {(r["name"], r["label"]): r for r in lines["reach"]}
    assert (
        reach["answer", "warning"]["offered"],
        reach["answer", "warning"]["missing"],
    ) == (
        False,
        [],
    )
    assert reach["lines", "text"]["missing"] == []


@pytest.mark.slow
def test_a_case_with_expectations_to_choose_from_is_shown_apart_in_the_reach(
    signed: TestClient, bench: Bench
) -> None:
    native = thread(signed, "configuration", NATIVE)
    [family] = signed.get("/api/families", params={"name": "crlf"}).json()

    def differential() -> tuple[list[int], list[int]]:
        shown = variation(signed, native)
        [found] = [r for r in shown["reach"] if (r["name"], r["label"]) == DIFFERENTIAL]
        return found["missing"], found["choosing"]

    assert differential() == ([], [])
    _ = another_expectation(bench, family["case"], {"diagnosis": {"pattern": "x"}})
    assert differential() == ([], [family["id"]])


@pytest.mark.slow
def test_an_unsaved_variation_is_linted_in_each_language_it_runs_in(
    signed: TestClient,
) -> None:
    web = thread(signed, "configuration", NATIVE_TOOLS)
    off = digest(signed, "reasoning", OFF)

    def codes(**params: Any) -> set[str]:
        shown = variation(signed, web, reasoning=off, **params)
        assert shown["skeleton"] != web["head"]["digest"]
        return {f["code"] for f in shown["findings"]}

    assert not {"language.unknown", "translations.missing"} & codes(tag="targets")
    left = variation(signed, web, reasoning=off)["languages"]
    assert [c["language"] for c in left if c["untranslated"]] == ["sv"]

    guided = thread(signed, "configuration", LINES_GUIDED)
    shown = variation(signed, guided, reasoning=off)
    english, swedish = shown["languages"]
    assert (english["language"], english["skeleton"]) == ("en", shown["skeleton"])
    assert (swedish["language"], swedish["translated"], swedish["refused"]) == (
        "sv",
        True,
        None,
    )
    assert swedish["skeleton"] not in (None, shown["skeleton"])
    assert not {"language.mixed", "translations.missing"} & {
        f["code"] for f in shown["findings"]
    }


@pytest.mark.slow
def test_a_judge_configuration_is_looked_at_as_a_judge(signed: TestClient) -> None:
    query = {"kind": "configuration", "purpose": "judge", "name": JUDGE}
    [judging] = signed.get("/api/threads", params={**query, "owner": "alice"}).json()
    shown = variation(signed, judging)
    assert shown["reach"] == [] and shown["findings"] == []
    assert "‹completion›" in str(shown["request"])


@pytest.mark.slow
def test_a_variation_the_bench_refuses_is_unprocessable(
    signed: TestClient, conn: Connection, bob: dict[str, str]
) -> None:
    mine = thread(signed, "configuration", LINES)
    off = digest(signed, "reasoning", OFF)
    store = Store(conn)
    registry = store.load([])
    untranslated = registry.add(Translations(into={"sv": {"Hello": "Hej"}}))
    _ = store.add(registry, [untranslated])
    path = f"/api/threads/{mine['id']}/variation"
    for params, said in (
        ({"prompt": off}, f"{off} isn't a stored chunk of prompt"),
        ({"prompt": ""}, "a configuration always holds its prompt"),
        ({"model": ""}, "a configuration always holds its model"),
    ):
        got = signed.get(path, params=params)
        assert got.status_code == 422, params
        assert got.json()["detail"].startswith(said)
    under = signed.get(path, params={"under": GPT_OSS_ARTIFACT}).json()
    assert (under["model"], under["findings"]) == (None, None)
    assert (
        under["problem"] == "lines runs under its model's handle: set its model instead"
    )

    swedish = signed.get(path, params={"translations": untranslated}).json()
    assert [c["refused"] for c in swedish["languages"]] == [
        None,
        "no translation into sv for 'List the plausible diagnoses, one per line, most "
        + "likely first.'",
    ]

    got = signed.get(path, params={"stack": off})
    assert got.status_code == 422
    assert [e["loc"] for e in got.json()["detail"]] == [["query", "stack"]]

    chunk = thread(signed, "reasoning", OFF)["id"]
    got = signed.get(f"/api/threads/{chunk}/variation")
    assert (got.status_code, got.json()) == (
        404,
        {"detail": f"no configuration {chunk} for alice", "code": "not_found"},
    )
    got = signed.get(path, headers=bob)
    assert (got.status_code, got.json()) == (
        404,
        {"detail": f"no configuration {mine['id']} for bob", "code": "not_found"},
    )


@pytest.mark.slow
def test_a_look_s_queries_don_t_grow_with_its_cases(
    signed: TestClient, db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    web = thread(signed, "configuration", NATIVE_TOOLS)
    counted = [0]
    execute = psycopg.Cursor.execute

    # Accommodating for the fixtures, which make the next test's database meanwhile:
    # only the look's database's queries count.
    def counting(cursor: psycopg.Cursor[Any], *args: Any, **kwargs: Any) -> Any:
        counted[0] += cursor.connection.info.dbname == db
        return execute(cursor, *args, **kwargs)

    monkeypatch.setattr(psycopg.Cursor, "execute", counting)

    def look(**params: Any) -> tuple[int, int]:
        counted[0] = 0
        shown = variation(signed, web, **params)
        return shown["reach"][0]["cases"], counted[0]

    # Accommodating for the components Store.get holds parsed: both looks are made once
    # before they are counted, so that neither counts reading what the other read.
    _ = look(tag="swedish"), look()
    (few, queries), (every, again) = look(tag="swedish"), look()
    assert few < every
    assert queries == again


@pytest.mark.slow
def test_a_fork_is_a_configuration_of_one_s_own(signed: TestClient) -> None:
    archives = thread(signed, "configuration", LINES, "archive")
    off = digest(signed, "reasoning", OFF)
    path = f"/api/threads/{archives['id']}/forks"
    asked = {"name": "terse", "parts": {"reasoning": off}}

    got = signed.post(path, json=asked)
    assert got.status_code == 201
    made = got.json()
    assert got.headers["location"] == f"/api/threads/{made['id']}"
    assert made.pop("findings") == []
    assert signed.get(got.headers["location"]).json() == made
    assert (made["kind"], made["name"], made["owner"]) == ("skeleton", "terse", "alice")
    assert made["forked_from"] == archives["head"]["id"]
    assert made["recipe"]["reasoning"] == off
    assert (
        made["head"]["digest"] == variation(signed, archives, reasoning=off)["skeleton"]
    )

    again = signed.post(path, json=asked)
    assert again.status_code == 201 and again.json()["id"] != made["id"]
    plain = signed.post(path, json={"name": "mine"}).json()
    assert plain["head"]["digest"] == archives["head"]["digest"]


@pytest.mark.slow
def test_an_edit_is_a_new_version_of_one_s_own_configuration(
    signed: TestClient,
) -> None:
    mine = thread(signed, "configuration", LINES)
    off = digest(signed, "reasoning", OFF)
    path = f"/api/threads/{mine['id']}/edits"
    seen = mine["head"]["id"]

    got = signed.post(path, json={"head": seen, "parts": {"reasoning": off}})
    assert got.status_code == 201
    edited = got.json()
    assert (edited["by"], edited["digest"]) == (
        "alice",
        variation(signed, mine, reasoning=off)["skeleton"],
    )
    assert (edited.pop("findings"), edited.pop("cases")) == ([], {})
    assert signed.get(path).json()[-1] == {**edited, "version": 2}

    now = edited["id"]
    again = signed.post(path, json={"head": now, "parts": {"reasoning": off}})
    assert again.status_code == 200
    assert again.json() == {**edited, "findings": [], "cases": {}}
    assert signed.post(path, json={"head": now}).status_code == 200
    moved = signed.post(path, json={"head": seen, "parts": {"reasoning": None}})
    assert moved.status_code == 409
    assert (
        f"has moved on since edit {seen}: its head is edit {now}"
        in (moved.json()["detail"])
    )

    back = signed.post(path, json={"head": now, "parts": {"reasoning": None}})
    assert back.status_code == 201
    assert [e["digest"] for e in signed.get(path).json()][-3:] == [
        mine["head"]["digest"],
        edited["digest"],
        mine["head"]["digest"],
    ]


@pytest.mark.slow
def test_only_one_s_own_configuration_is_edited_and_a_seen_one_forked(
    signed: TestClient, bob: dict[str, str]
) -> None:
    archives = thread(signed, "configuration", LINES, "archive")
    got = signed.post(
        f"/api/threads/{archives['id']}/edits", json={"head": archives["head"]["id"]}
    )
    assert (got.status_code, got.json()) == (
        404,
        {"detail": f"no configuration {archives['id']} of yours", "code": "not_found"},
    )

    mine = thread(signed, "configuration", LINES)
    head = mine["head"]["id"]
    for path, body in (
        (f"/api/threads/{mine['id']}/forks", {"name": "bob's"}),
        (f"/api/threads/{mine['id']}/edits", {"head": head}),
    ):
        got = signed.post(path, json=body, headers=bob)
        assert (got.status_code, got.json()) == (
            404,
            {"detail": f"no configuration {mine['id']} for bob", "code": "not_found"},
        )

    off = digest(signed, "reasoning", OFF)
    forks, edits = (f"/api/threads/{mine['id']}/{to}" for to in ("forks", "edits"))
    unvalidated: list[tuple[str, dict[str, Any], list[str]]] = [
        (forks, {"name": ""}, ["body", "name"]),
        (forks, {"parts": {}}, ["body", "name"]),
        (edits, {"head": head, "parts": {"stack": off}}, ["body", "parts", "stack"]),
        (edits, {"parts": {}}, ["body", "head"]),
    ]
    for path, body, where in unvalidated:
        got = signed.post(path, json=body)
        assert got.status_code == 422
        assert [e["loc"] for e in got.json()["detail"]] == [where]
    got = signed.post(edits, json={"head": head, "parts": {"prompt": off}})
    assert (got.status_code, got.json()) == (
        422,
        {"detail": f"{off} isn't a stored chunk of prompt", "code": "refused"},
    )
    assert signed.get(edits).json()[-1] == {**mine["head"], "version": 1}


def test_trying_forking_and_editing_need_a_session(
    client: TestClient, bench: Bench
) -> None:
    mine = bench.thread(LINES, "configuration")[0].thread
    assert client.get(f"/api/threads/{mine}/variation").status_code == 401
    for path in (f"/api/threads/{mine}/forks", f"/api/threads/{mine}/edits"):
        assert client.post(path, json={"name": "x"}).status_code == 401

    _ = sign_in(client, **{"Sec-Fetch-Site": "same-origin"})
    elsewhere = {"Sec-Fetch-Site": "cross-site"}
    got = client.post(
        f"/api/threads/{mine}/forks", json={"name": "x"}, headers=elsewhere
    )
    assert got.status_code == 403
