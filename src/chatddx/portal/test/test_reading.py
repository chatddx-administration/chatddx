import html
import json
import re
from collections import Counter
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from markupsafe import escape

from chatddx import settings
from chatddx.api.state import AppState
from chatddx.portal.test.helpers import (
    compose_props,
    ran_template,
    run_title,
    said,
    shown,
)
from chatddx.store import People
from chatddx.store.store import Connection
from chatddx.test.world import (
    GPT_OSS,
    GPT_OSS_ARTIFACT,
    GPT_OSS_MODEL,
    MISTRAL,
    MISTRAL_ARTIFACT,
    MISTRAL_MODEL,
    QWEN,
    QWEN_ARTIFACT,
    QWEN_BARE,
    QWEN_BARE_ARTIFACT,
    QWEN_MODEL,
    REMOTE,
    TEST,
    UNKNOWN_MODEL,
)

__all__ = ["ran_template"]


@pytest.mark.usefixtures("alice")
@pytest.mark.slow
def test_a_run_is_titled_by_its_parts_in_the_locale_asked_for(
    signed: TestClient,
) -> None:
    [run] = [
        r
        for r in signed.get("/api/runs").json()
        if r["titled"]["case"]
        and not r["titled"]["case"]["appendices"]
        and len(r["seeds"]) == 1
        and not r["titled"]["greedy"]
    ][:1]
    titled = run["titled"]
    asked = signed.get(f"/runs/{run['id']}", headers={"accept-language": "sv"})
    case = titled["case"]["name"]
    swedish = (
        f"{case} med `{titled['name']}` på {titled['at']} (seed {run['seeds'][0]})"
    )
    assert escape(swedish) in asked.text
    assert escape(run_title(run)) in shown(signed, f"/runs/{run['id']}")


@pytest.mark.slow
def test_a_person_s_runs_are_listed_and_each_is_read_on_its_page(
    signed: TestClient,
) -> None:
    runs = signed.get("/api/runs").json()
    assert runs
    listed = shown(signed, "/runs")
    left = {r["id"] for r in signed.get("/api/runs", params={"unscored": True}).json()}
    listed_left = shown(signed, "/runs?left=true")
    for r in runs:
        assert f'href="/runs/{r["id"]}"' in listed
        assert (f'href="/runs/{r["id"]}"' in listed_left) == (r["id"] in left)
        page = shown(signed, f"/runs/{r['id']}")
        detail = signed.get(f"/api/runs/{r['id']}").json()
        assert escape(run_title(r)) in page
        for item in detail["items"]:
            assert f">{item['outcome']}</span>" in page
        row = listed.split(f'value="{r["id"]}"', 1)[1].split("</tr>", 1)[0]
        counted = Counter(item["outcome"] for item in detail["items"])
        assert all(f">{n} {said}</span>" in row for said, n in counted.items())
        if rest := len(r["cases"]) * len(r["seeds"]) - len(detail["items"]):
            assert f"{rest} {'missing' if r['finished'] else 'to go'}" in row
        for graded in detail["scores"]:
            assert escape(graded["name"]) in page
        assert 'id="item-1"' in page or not detail["items"]


@pytest.mark.slow
def test_a_run_s_page_shows_its_answers_and_what_its_scores_hold(
    signed: TestClient,
) -> None:
    runs = signed.get("/api/runs").json()
    judged = next(
        r for r in runs if signed.get(f"/api/runs/{r['id']}").json()["scores"]
    )
    page = shown(signed, f"/runs/{judged['id']}")
    for item in signed.get(f"/api/runs/{judged['id']}/items").json():
        answer = item["answer"]["value"]
        if isinstance(answer, str):
            assert escape(answer) in page
        elif answer is not None:
            assert escape(json.dumps(answer, indent=2, ensure_ascii=False)) in page
    assert ">Mean</td>" in page


@pytest.mark.slow
def test_a_first_mention_is_shown_where_it_is_in_the_answer(signed: TestClient) -> None:
    for r in signed.get("/api/runs").json():
        for graded in signed.get(f"/api/runs/{r['id']}").json()["scores"]:
            body = signed.get(f"/api/components/{graded['scorer']}").json()["body"]
            at = {
                i for i, v in enumerate(body["views"]) if v["metric"] == "first_mention"
            }
            found = [
                i["value"]
                for i in graded["items"]
                if i["view"] in at and i["value"] is not None
            ]
            if found:
                page = shown(signed, f"/runs/{r['id']}")
                assert all(f">@{int(v)}</td>" in page for v in found)
                compared = shown(signed, f"/runs/compare?run={r['id']}")
                assert all(f">@{int(graded['means'][v])} " in compared for v in at)
                return
    pytest.fail("no run is scored with a first mention")


@pytest.mark.slow
def test_another_s_run_isn_t_found_by_a_page_or_the_api(
    client: TestClient, signed: TestClient, conn: Connection
) -> None:
    [run, *_] = signed.get("/api/runs").json()
    _ = signed.post("/sign-out")
    People(conn).set_password(People(conn).add("bob", "Bob").id, "bob's password")
    form = {"login": "bob", "password": "bob's password", "next": "/"}
    assert client.post("/sign-in", data=form).status_code == 303
    page = client.get(f"/runs/{run['id']}")
    assert page.status_code == 404 and page.headers["content-type"].startswith(
        "text/html"
    )
    assert "Not found" in page.text and f"no run {run['id']} of yours" in page.text
    api = client.get(f"/api/runs/{run['id']}")
    assert (api.status_code, api.json()["code"]) == (404, "not_found")


@pytest.mark.slow
def test_a_configuration_is_read_with_its_recipe_in_compose(
    signed: TestClient,
) -> None:
    query = {"kind": "configuration"}
    [first, *_] = signed.get("/api/threads", params=query).json()
    page = shown(signed, f"/compose/{first['id']}")
    assert compose_props(page)["drafted"] is not None
    assert "Version 1" in page and "take scripts" in page
    scorer = signed.get("/api/threads", params={"kind": "scorer"}).json()[0]
    assert signed.get(f"/compose/{scorer['id']}").status_code == 404


@pytest.mark.slow
def test_cases_are_listed_by_tag_in_the_library_and_read_without_their_vignette(
    signed: TestClient,
) -> None:
    families = signed.get("/api/families").json()
    listed = shown(signed, "/library?kind=case")
    assert "None is begun here" in listed
    for f in families:
        assert f'href="/cases/{f["id"]}"' in listed
    tagged = signed.get("/api/families", params={"tag": "swedish"}).json()
    page = shown(signed, "/library?kind=case&tag=swedish")
    assert {f["id"] for f in families if f'href="/cases/{f["id"]}"' in page} == {
        f["id"] for f in tagged
    }
    [noted] = [f for f in families if f["name"] == "noted"]
    vignette = signed.get(f"/api/families/{noted['id']}/vignette").json()
    first = escape(vignette["text"].strip().splitlines()[0])
    page = shown(signed, f"/cases/{noted['id']}")
    assert first not in page and f'href="/cases/{noted["id"]}/vignette"' in page
    for case in signed.get(f"/api/families/{noted['id']}").json()["cases"]:
        for expected in case["expectations"]:
            assert escape(expected["title"]) in page
    assert first in shown(signed, f"/cases/{noted['id']}/vignette")
    assert signed.get("/families").status_code == 404


@pytest.mark.slow
def test_the_world_lists_what_the_portal_started_in_by_handle_facts_and_engine(
    signed: TestClient,
) -> None:
    page = shown(signed, "/world")
    assert str(TEST / "inventory.toml") in page and str(TEST / "facts.toml") in page
    threads = {
        kind: {t["name"]: t["id"] for t in _threads(signed, kind)}
        for kind in ("model", "engine", "facts")
    }
    for handle, at in (
        (QWEN_ARTIFACT, QWEN),
        (QWEN_BARE_ARTIFACT, QWEN_BARE),
        (GPT_OSS_ARTIFACT, GPT_OSS),
        (MISTRAL_ARTIFACT, MISTRAL),
        (UNKNOWN_MODEL, REMOTE),
    ):
        card = _card(page, f"handle-{threads['model'][handle]}")
        assert f'href="#endpoint-{at}"' in card
        assert f'href="#engine-{threads["engine"][at]}"' in card
    for e in signed.get("/api/endpoints").json():
        assert escape(e["name"]) in page and escape(e["url"]) in page
    assert set(threads["facts"].values()) == {
        int(i) for i in re.findall(r'id="facts-(\d+)"', page)
    }
    gpt_oss = _text(page, f"facts-{threads['facts'][GPT_OSS_MODEL]}")
    assert "21 billion, 3.6 billion active" in gpt_oss
    assert f"sends {json.dumps({'reasoning_effort': 'low'})}" in gpt_oss
    mistral = _text(page, f"facts-{threads['facts'][MISTRAL_MODEL]}")
    assert "refused: test/mistral-7b's chat template has no tool calls" in mistral
    assert "{" not in mistral
    qwen = _text(page, f"engine-{threads['engine'][QWEN]}")
    assert "vLLM 0.24.0+fake, from chatddx fake-vllm" in qwen
    assert "--tool-call-parser hermes" in qwen and "kept at /dev/null on fake" in qwen
    assert str(TEST / "vignettes") in page and "texts typed into the database" in page
    assert "CHATDDX_TEST_REMOTE" in page and QWEN_MODEL in page
    qwen_handle = threads["model"][QWEN_ARTIFACT]
    assert (
        f'<span class="font-medium">verdict</span> to <a href="#handle-{qwen_handle}">'
        + f"{QWEN_ARTIFACT}</a>"
    ) in page
    assert 'href="/world"' in page and signed.get("/models").status_code == 404


@pytest.mark.slow
def test_a_handle_and_an_engine_no_endpoint_serves_say_so_and_come_last(
    served: FastAPI, signed: TestClient
) -> None:
    held = served.state.chatddx
    endpoints = {n: e for n, e in held.inventory.endpoints.items() if n != QWEN}
    served.state.chatddx = AppState(
        held.conninfo,
        held.inventory.model_copy(update={"endpoints": endpoints}),
        held.listener,
    )
    page = shown(signed, "/world")
    handle = f"handle-{_threads(signed, 'model', QWEN_ARTIFACT)}"
    engine = f"engine-{_threads(signed, 'engine', QWEN)}"
    assert "no endpoint serves its weights, so it can't be picked" in _text(
        page, handle
    )
    assert "no endpoint serves it" in _text(page, engine)
    for last, section in ((handle, "handles"), (engine, "engines")):
        within = page[page.index(f'id="{section}"') :]
        assert (
            re.findall(rf'id="{section[:-1]}-\d+"', within.split("</section>")[0])[-1]
            == f'id="{last}"'
        )


def _threads(client: TestClient, kind: str, name: str | None = None) -> Any:
    found = client.get("/api/threads", params={"kind": kind}).json()
    return found if name is None else next(t["id"] for t in found if t["name"] == name)


def _card(page: str, anchor: str) -> str:
    return page.split(f'id="{anchor}"', 1)[1].split("</details>", 1)[0]


def _text(page: str, anchor: str) -> str:
    return html.unescape(said(f"<main{_card(page, anchor)}"))


@pytest.mark.slow
def test_runs_are_paged_on_the_server_and_found_in_by_their_titles(
    signed: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    every = signed.get("/api/runs", params={"limit": 200}).json()
    assert len(every) > 2
    monkeypatch.setattr(settings, "ROWS_PER_PAGE", 2)
    pages = [shown(signed, f"/runs?page={n}") for n in range(1, len(every) // 2 + 2)]
    for r in every:
        assert sum(f'href="/runs/{r["id"]}"' in p for p in pages) == 1
    assert 'name="q"' in pages[0] and 'href="/runs?page=2"' in pages[0]
    assert "page 1" in said(pages[0]) and 'href="/runs?page=1"' in pages[1]

    run = every[0]
    word = run["titled"]["name"].split()[0].upper()
    found = signed.get("/api/runs", params={"q": word, "limit": 200}).json()
    assert run["id"] in {r["id"] for r in found}
    assert signed.get("/api/runs", params={"q": f"{word} no-such-word"}).json() == []
    page = shown(signed, f"/runs?q={word}")
    assert f'value="{escape(word)}"' in page and "show every one" in page
    if len(found) > 2:
        assert f'href="/runs?page=2&amp;q={word}"' in page


@pytest.mark.slow
def test_a_list_is_found_in_from_as_many_rows_as_a_page_holds_and_paged_past_them(
    signed: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = len(signed.get("/api/threads", params={"kind": "model"}).json())

    def section(rows: int) -> str:
        monkeypatch.setattr(settings, "ROWS_PER_PAGE", rows)
        page = shown(signed, "/world")
        return page[page.index('id="handles"') : page.index('id="facts"')]

    assert "data-finding" not in section(handles + 1)
    held = section(handles)
    assert "data-paged" in held and "data-finding" in held and "data-pages" not in held
    assert "data-pages" in section(handles - 1)


@pytest.mark.slow
def test_a_run_s_items_and_their_scores_are_paged_with_the_mean_kept_below(
    signed: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = signed.get("/api/runs", params={"limit": 200}).json()
    details = [signed.get(f"/api/runs/{r['id']}").json() for r in runs]
    run = next(d for d in details if len(d["items"]) > 1 and d["scores"])
    monkeypatch.setattr(settings, "ROWS_PER_PAGE", 1)
    page = shown(signed, f"/runs/{run['id']}")
    listed = page.split("<tbody data-paged>", 1)[1].split("</tbody>", 1)[0]
    assert listed.count('href="#item-') == len(run["items"])
    sections = page.split("<div data-paged>", 1)[1]
    assert all(f'id="item-{n}"' in sections for n in range(1, len(run["items"]) + 1))
    assert page.count("<nav data-pages hidden") == page.count("<tbody data-paged>") + 1
    for footer in page.split("<tfoot>")[1:]:
        assert "Mean" in footer.split("</tfoot>", 1)[0]


@pytest.mark.usefixtures("alice")
@pytest.mark.slow
def test_what_a_page_can_t_find_is_a_page_and_the_api_s_stays_json(
    signed: TestClient,
) -> None:
    page = signed.get("/nowhere")
    assert page.status_code == 404 and "Not found" in page.text
    assert 'aria-current="page"' not in page.text and "Sign out" in page.text
    assert signed.get("/api/nowhere").json()["code"] == "not_found"
    assert signed.get("/runs/not-a-run").status_code == 422


def test_a_value_the_store_can_t_keep_is_refused_by_a_page_and_the_api(
    signed: TestClient,
) -> None:
    large = "9" * 30
    for path in (f"/compose/{large}", f"/review/{large}", f"/threads/{large}"):
        page = signed.get(path)
        assert page.status_code == 422, path
        assert page.headers["content-type"].startswith("text/html")
        assert "bigint" not in page.text
    for path in (
        f"/api/threads/{large}",
        f"/api/families/{large}",
        "/api/components/%00",
    ):
        got = signed.get(path)
        assert (got.status_code, got.json()["code"]) == (422, "refused"), path
        assert "can't be kept" in got.json()["detail"]
