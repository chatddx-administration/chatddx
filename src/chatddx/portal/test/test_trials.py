import time
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from markupsafe import escape

from chatddx.api.test.helpers import endpoint, family, thread
from chatddx.catalog.titles import display_digest
from chatddx.factors.engine import model_of
from chatddx.identity import Person
from chatddx.portal.test.helpers import said, shown, submitted, world_served
from chatddx.store import Catalog, Store
from chatddx.store.store import Connection
from chatddx.test.world import JUDGE, LINES, LINES_GUIDED, QWEN, QWEN_ARTIFACT

__all__ = ["world_served"]


def begun(signed: TestClient, *families: str) -> str:
    picked = "&".join(f"family={family(signed, f)['id']}" for f in families)
    return f"/library/new?kind=trial&{picked}&expectation_schema=&owner="


def written(signed: TestClient, action: str, name: str) -> Any:
    page = shown(signed, action)
    given = {
        **submitted(page, action),
        "name": [name],
        "f.skeleton": [thread(signed, "configuration", LINES_GUIDED)["head"]["digest"]],
        "f.engine": [endpoint(signed, QWEN)["engine"]],
    }
    return signed.post(action, data=given)


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_trial_is_begun_of_the_picked_cases_and_run(
    signed: TestClient,
) -> None:
    none = shown(signed, "/library?kind=trial")
    assert "None you see." in none and 'href="/review">Review</a>' in none
    tab = shown(signed, "/library?kind=case")
    assert 'formaction="/library/new"' in tab and 'name="kind" value="trial"' in tab
    action = begun(signed, "nfd", "svenska")
    page = shown(signed, action)
    assert 'name="f.cases"' not in page and 'name="f.cleanup"' in page
    assert f">{QWEN_ARTIFACT}</option>" in page
    query = {"kind": "configuration", "purpose": "judge", "name": JUDGE}
    judges = signed.get("/api/threads", params=query).json()
    assert judges
    assert not [j for j in judges if f'value="{j["head"]["digest"]}"' in page]
    [seeds] = submitted(page, action)["f.seeds"]
    assert len(seeds.split()) == 1

    got = written(signed, action, "swedish")
    assert got.status_code == 303, got.text[:500]
    path = got.headers["location"]
    made = signed.get(f"/api{path}").json()
    assert made["language"] == "sv"
    page = shown(signed, path)
    assert f">{escape(LINES_GUIDED)}, in Swedish</option>" in page
    assert f'href="/lab/run?trial={made["id"]}"' in page and "None of yours." in page
    again = signed.post(f"{path}/edit", data=submitted(page, f"{path}/edit"))
    assert again.status_code == 303
    assert len(signed.get(f"/api{path}/edits").json()) == 1

    got = written(signed, begun(signed, "crlf", "nfd"), "mixed")
    assert (
        got.status_code == 422
        and "in one language, not in English and Swedish" in got.text
    )

    tab = shown(signed, "/library?kind=trial")
    assert f'name="trial" value="{made["id"]}"' in tab
    page = shown(signed, f"/lab/run?trial={made['id']}")
    assert QWEN in page and "Run it" in page
    form = {**submitted(page, "/lab/run"), "score": []}
    got = signed.post("/lab/run", data=form)
    assert got.status_code == 303, got.text[:500]
    run = got.headers["location"]
    for _ in range(500):
        if signed.get(f"/api{run}").json()["finished"]:
            break
        time.sleep(0.02)
    assert f'href="{path}">swedish</a>' in shown(signed, run)
    assert f'href="{run}"' in shown(signed, path)

    assert signed.get("/lab/run?trial=1").status_code == 404
    got = signed.post("/lab/run", data={"version": [], "order": "sideways"})
    assert got.status_code == 422 and escape("no order 'sideways'") in got.text
    got = signed.post("/lab/run", data={"version": [""], "trial": ["7", "8"]})
    assert (got.status_code, got.headers["location"]) == (
        303,
        "/lab/run?trial=7&trial=8",
    )
    got = signed.get("/runs/compare")
    assert (got.status_code, got.headers["location"]) == (303, "/runs")


@pytest.mark.slow
def test_a_trial_s_forms_from_another_site_start_nothing(signed: TestClient) -> None:
    elsewhere = {"Sec-Fetch-Site": "cross-site"}
    assert signed.post("/lab/run", headers=elsewhere).status_code == 403


@pytest.mark.slow
def test_a_world_broken_under_a_running_app_is_paged_with_its_boot_check(
    signed: TestClient,
    paged: TestClient,
    served: FastAPI,
    conn: Connection,
    alice: Person,
) -> None:
    lines = thread(signed, "configuration", LINES)
    action = begun(signed, "nfd")
    inventory = served.state.chatddx.inventory
    weights = model_of(inventory.endpoint(QWEN).engine, Store(conn).get).digest
    _ = Catalog(conn).create(weights, alice.id, name="twin")
    broken = (
        f"RuntimeError: {display_digest(weights)} is held by 2 model threads, not one: "
        + "fix boot-check src/chatddx/bench/handles.py:broken"
    )
    for path in (action, f"/compose/{lines['id']}"):
        got = paged.get(path)
        assert got.status_code == 500, (path, said(got.text)[:300])
        assert said(got.text).startswith(
            f"> Something went wrong Copy this and send it to drift@chatddx.com: {broken} "
        )
