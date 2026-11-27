import re
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from markupsafe import escape
from pydantic import JsonValue

from chatddx.api.test.helpers import thread
from chatddx.bench import Bench
from chatddx.bench.test.helpers import correct_facts
from chatddx.catalog.titles import display_digest
from chatddx.factors.engine import FileDigest, LocalModel
from chatddx.identity import Person
from chatddx.inventory import Inventory
from chatddx.locale import Locales
from chatddx.locale.test.helpers import catalog
from chatddx.portal.test.helpers import compose_props, ran_template, said, shown
from chatddx.scripted.test.helpers import held
from chatddx.store import Store
from chatddx.store.store import Connection
from chatddx.test.helpers import alices_bench
from chatddx.test.world import (
    COMPARED,
    JUDGE,
    LINES,
    LINES_INSTRUCTED,
    OFF,
    QWEN_MODEL,
    TEST,
)

__all__ = ["alices_bench", "ran_template"]


@pytest.mark.slow
def test_compose_leads_to_one_s_first_configuration(signed: TestClient) -> None:
    got = signed.get("/compose")
    assert got.status_code == 303
    listed = signed.get(
        "/api/threads", params={"kind": "configuration", "owner": "alice"}
    ).json()
    first = min(listed, key=lambda t: t["name"] or t["title"])
    assert got.headers["location"] == f"/compose/{first['id']}"
    assert 'href="/compose"' in shown(signed, "/runs")


@pytest.mark.slow
def test_compose_lists_the_configurations_review_runs_a_case_under(
    signed: TestClient,
) -> None:
    mine = thread(signed, "configuration", LINES_INSTRUCTED)
    page = shown(signed, f"/compose/{mine['id']}")
    listed = signed.get(
        "/api/threads",
        params={"kind": "configuration", "purpose": "generation", "owner": "alice"},
    ).json()
    names = sorted(t["name"] or t["title"] for t in listed)
    listing = page.split('<nav aria-label="Configurations"', 1)[1].split("</nav>", 1)[0]
    assert re.findall(r'href="/compose/\d+"[^>]*>([^<]*)</a>', listing) == names
    assert "<details" not in page
    assert f'href="/compose/{mine["id"]}" aria-current="page"' in page
    assert "<h2>Scores</h2>" not in page


def test_compose_lists_a_fork_under_what_it_was_forked_from(
    signed: TestClient,
) -> None:
    mine = thread(signed, "configuration", LINES_INSTRUCTED)
    saves = f"/api/threads/{mine['id']}/saves"
    base: dict[str, JsonValue] = {"head": mine["head"]["id"], "chunks": {}}
    fork = signed.post(saves, json={**base, "name": "a fork"}).json()
    alone = signed.post(saves, json={**base, "name": "alone", "independent": True})
    assert alone.status_code == 201, alone.json()
    page = shown(signed, f"/compose/{mine['id']}")
    under = page.split(f'aria-label="Forked from {LINES_INSTRUCTED}"', 1)[1]
    under = under.split("</ol>", 1)[0]
    assert f'href="/compose/{fork["id"]}"' in under
    assert f'href="/compose/{alone.json()["id"]}"' not in under
    assert f'href="/compose/{alone.json()["id"]}"' in page


@pytest.mark.slow
def test_weights_no_model_thread_holds_are_a_whoops_where_they_are_tried(
    signed: TestClient, paged: TestClient, bench: Bench, served: FastAPI, tmp_path: Path
) -> None:
    store = Store(bench.conn)
    registry = store.load([])
    weights = registry.add(
        LocalModel(
            repo=QWEN_MODEL,
            revision="unheld",
            files=(FileDigest(path="none", sha256="0" * 64),),
        )
    )
    _ = store.add(registry, [weights])
    bench.conn.commit()
    lines = thread(signed, "configuration", LINES)
    whoops = "The model has no handle and can't be used."
    pass_on = (
        f"{display_digest(weights)} is held by no model thread: check the RuntimeErrors"
    )
    got = paged.get(f"/compose/{lines['id']}?model={weights}")
    assert got.status_code == 500, said(got.text)[:300]
    assert said(got.text).startswith(
        f"> Something went wrong {escape(whoops)} Copy this and send it to "
        + f"drift@chatddx.com: {pass_on} "
    )
    asked = paged.get(f"/api/threads/{lines['id']}/variation?model={weights}")
    assert (asked.status_code, asked.json()) == (
        500,
        {"code": "whoops", "detail": whoops, "pass_on": pass_on},
    )

    served.state.locales = Locales(
        catalog(
            tmp_path,
            f"""
            msgctxt "whoops"
            msgid "{whoops}"
            msgstr "Ingen modell i biblioteket håller vikterna: ta en annan så länge."
            """,
        )
    )
    sv = paged.get(
        f"/compose/{lines['id']}?model={weights}", headers={"accept-language": "sv"}
    )
    assert (
        f"Ingen modell i biblioteket håller vikterna: ta en annan så länge. Copy this and send it to drift@chatddx.com: {pass_on} "
        in said(sv.text)
    )


@pytest.mark.slow
def test_a_judge_s_configuration_is_written_in_compose_and_a_chunk_isn_t_found(
    signed: TestClient,
) -> None:
    prompt = thread(signed, "prompt", "case")
    assert signed.get(f"/compose/{prompt['id']}").status_code == 404
    judge = signed.get(
        "/api/threads",
        params={"kind": "configuration", "purpose": "judge", "name": JUDGE},
    ).json()[0]
    given = compose_props(shown(signed, f"/compose/{judge['id']}"))
    assert given["configuration"]["id"] == judge["id"]
    assert given["drafted"]["chunks"]["prompt"]["purpose"] == "judge"


@pytest.mark.slow
def test_runs_picked_on_the_runs_page_are_compared(
    signed: TestClient, bench: Bench
) -> None:
    runs = [held(bench, name).run for name in COMPARED]
    page = shown(signed, "/runs")
    assert 'action="/runs/compare"' in page
    assert f'name="run" value="{runs[0]}" form="compare"' in page

    query = "&".join(f"run={r}" for r in runs)
    text = said(shown(signed, f"/runs/compare?{query}"))
    assert re.search(r"lines · differential 0\.75 \(2\) 0\.50 \(2\) 0\.00 \(2\)", text)
    assert re.search(r"By item, under \w+ · [\w-]+ ", text)
    assert "Held by only some" not in text
    appendix = held(bench, "appendix").run
    text = said(shown(signed, f"/runs/compare?run={runs[0]}&run={appendix}"))
    assert "A mean is over the 0 items" in text and "By item" not in text
    assert "Held by only some" in text
    assert signed.get("/runs/compare").headers["location"] == "/runs"


@pytest.mark.slow
def test_compose_holds_the_variation_its_address_gives(
    signed: TestClient,
) -> None:
    mine = thread(signed, "configuration", LINES)
    off = thread(signed, "reasoning", OFF)["head"]["digest"]
    page = shown(signed, f"/compose/{mine['id']}?reasoning={off}")

    given = compose_props(page)
    drafted = given["drafted"]
    held = signed.get(f"/api/components/{off}").json()["body"]
    reasoning = drafted["chunks"]["reasoning"]
    assert reasoning.items() <= held.items() and reasoning["kind"] == held["kind"]
    assert "translations" not in drafted["chunks"]
    assert set(drafted["schemas"]) == set(drafted["chunks"])
    assert given["me"] == "alice" and given["configuration"]["id"] == mine["id"]

    recipe = signed.get(f"/api/threads/{mine['id']}").json()["recipe"]
    assert drafted["model"] == recipe["model"]
    models = [t["head"]["digest"] for t in given["modelChoices"]]
    assert recipe["model"] in models and len(models) == len(set(models))


@pytest.mark.slow
def test_a_fork_is_updated_from_its_origin_on_its_page(signed: TestClient) -> None:
    mine = thread(signed, "configuration", LINES)
    off = thread(signed, "reasoning", OFF)
    forks = f"/api/threads/{mine['id']}/forks"
    fork = signed.post(
        forks, json={"name": "terse", "parts": {"reasoning": off["head"]["digest"]}}
    ).json()
    path = f"/compose/{fork['id']}"
    assert "Its origin has a newer version." not in shown(signed, path)

    greedy = thread(signed, "sampling", "greedy")["head"]["digest"]
    edits = f"/api/threads/{mine['id']}/edits"
    got = signed.post(
        edits, json={"head": mine["head"]["id"], "parts": {"sampling": greedy}}
    )
    assert got.status_code == 201
    page = shown(signed, path)
    assert "Its origin has a newer version." in page
    assert f"reasoning</span>: yours keeps {OFF} over —" in page
    assert "Its origin has a newer version." not in shown(
        signed, f"/compose/{mine['id']}"
    )

    head = signed.get(f"/api/threads/{fork['id']}").json()["head"]
    got = signed.post(
        f"/threads/{fork['id']}/update", data={"head": head["id"], "next": path}
    )
    assert (got.status_code, got.headers["location"]) == (303, path)
    assert "Its origin has a newer version." not in shown(signed, path)
    followed = signed.get(f"/api/threads/{fork['id']}/variation").json()
    assert {p["part"]: p["digest"] for p in followed["parts"]}["sampling"] == greedy


@pytest.mark.slow
def test_a_configuration_is_updated_to_its_corrected_facts_from_its_pages(
    signed: TestClient, conn: Connection, alice: Person
) -> None:
    mine = thread(signed, "configuration", LINES)
    path = f"/compose/{mine['id']}"
    corrected = "were corrected where they change what it sends"
    assert corrected not in shown(signed, path)

    bench = Bench(conn, alice, Inventory.load(TEST / "inventory.toml"))
    recommended: dict[str, JsonValue] = {"on": {"temperature": 0.2}}
    _ = correct_facts(bench, QWEN_MODEL, sampling={"recommended": recommended})
    page = shown(signed, path)
    assert corrected in page and ">Update<" in page
    page = shown(signed, f"/threads/{mine['id']}")
    assert corrected in page and f'action="/threads/{mine["id"]}/update"' in page

    got = signed.post(
        f"/threads/{mine['id']}/update",
        data={"head": mine["head"]["id"], "next": path},
    )
    assert (got.status_code, got.headers["location"]) == (303, path)
    assert corrected not in shown(signed, path)
    request = signed.get(f"/api/threads/{mine['id']}/variation").json()["request"]
    assert request["temperature"] == 0.2


@pytest.mark.slow
def test_its_versions_are_stepped_through_keeping_what_is_set(
    signed: TestClient,
) -> None:
    mine = thread(signed, "configuration", LINES)
    first = mine["head"]["id"]
    off = thread(signed, "reasoning", OFF)["head"]["digest"]
    edits = f"/api/threads/{mine['id']}/edits"
    later = signed.post(edits, json={"head": first, "parts": {"reasoning": off}})
    latest = later.json()["id"]
    path = f"/compose/{mine['id']}"

    greedy = thread(signed, "sampling", "greedy")["head"]["digest"]
    page = shown(signed, f"{path}?head={first}&sampling={greedy}")
    assert "Version 1 of 2" in page and "Newer version: saved" in page
    kept = urlencode({"sampling": greedy})
    assert f'href="?{kept}" data-head="{latest}"' in page
    assert compose_props(page)["head"] == first

    page = shown(signed, path)
    assert "Version 2 of 2" in page and "Newer version: saved" not in page
    assert f'href="?head={first}" data-head="{first}"' in page
    assert compose_props(page)["drafted"]["chunks"]["reasoning"] is not None

    back = signed.post(
        f"/threads/{mine['id']}/revert", data={"head": latest, "edit": first}
    )
    assert back.status_code == 303
    restored = signed.get(edits).json()[-1]
    assert restored["version"] == 1
    page = shown(signed, path)
    assert "Version 1 of 2" in page and "Newer version: saved" not in page
    assert f'href="?head={latest}" data-head="{latest}"' in page
    page = shown(signed, f"{path}?head={first}")
    assert "Version 1 of 2" in page and "Newer version: saved" not in page
    page = shown(signed, f"{path}?head={latest}")
    assert "Version 2 of 2" in page and "Newer version: saved" in page
    assert f'href="?" data-head="{restored["id"]}"' in page


@pytest.mark.slow
def test_a_variation_the_bench_refuses_is_a_page_of_its_own(
    signed: TestClient,
) -> None:
    mine = thread(signed, "configuration", LINES)
    archives = thread(signed, "configuration", LINES, "archive")
    off = thread(signed, "reasoning", OFF)["head"]["digest"]
    path = f"/compose/{mine['id']}"
    for query, status, why in (
        (f"prompt={off}", 422, f"{off} isn&#39;t a stored chunk of prompt"),
        (f"head={archives['head']['id']}", 404, "no edit"),
        ("stack=x", 422, "query.stack: Extra inputs are not permitted"),
    ):
        got = signed.get(f"{path}?{query}")
        assert got.status_code == status, query
        assert got.headers["content-type"].startswith("text/html")
        assert why in got.text, (query, got.text[:2000])


@pytest.mark.slow
def test_a_run_links_the_version_it_ran_else_one_holding_its_skeleton(
    signed: TestClient,
) -> None:
    runs = signed.get("/api/runs", params={"limit": 200}).json()
    configurations = signed.get(
        "/api/threads", params={"kind": "configuration", "owner": "alice"}
    ).json()
    heads = {c["head"]["digest"]: c for c in configurations}
    run = next(r for r in runs if r["skeleton"] in heads)
    ran = heads[run["skeleton"]]
    assert f'href="/compose/{ran["id"]}"' in shown(signed, f"/runs/{run['id']}")

    off = thread(signed, "reasoning", OFF)["head"]["digest"]
    edits = f"/api/threads/{ran['id']}/edits"
    got = signed.post(
        edits, json={"head": ran["head"]["id"], "parts": {"reasoning": off}}
    )
    assert got.status_code == 201
    page = shown(signed, f"/runs/{run['id']}")
    assert f'href="/compose/{ran["id"]}?head={ran["head"]["id"]}"' in page
    assert "an earlier version" in page

    deleted = signed.patch(f"/api/threads/{ran['id']}", json={"deleted": True})
    assert deleted.status_code == 200
    archives = thread(signed, "configuration", ran["name"], "archive")
    page = shown(signed, f"/runs/{run['id']}")
    assert f'href="/compose/{archives["id"]}"' in page
