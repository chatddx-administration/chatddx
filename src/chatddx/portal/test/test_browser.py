import json
import re
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import (
    Browser,
    Dialog,
    Error,
    Locator,
    Page,
    Route,
    expect,
    sync_playwright,
)

from chatddx import settings
from chatddx.identity import Person
from chatddx.inventory import Inventory
from chatddx.locale import Locales
from chatddx.locale.test.helpers import catalog
from chatddx.portal.assets import Assets
from chatddx.portal.test.helpers import world_served
from chatddx.store import Store
from chatddx.store.store import Connection
from chatddx.test.helpers import PASSWORD
from chatddx.test.world import (
    JUDGE,
    LINES,
    LINES_GUIDED,
    QWEN,
    QWEN_ARTIFACT,
    QWEN_BARE_ARTIFACT,
    faked,
)

__all__ = ["world_served"]

pytestmark = [pytest.mark.slow, pytest.mark.browser]


def _settled(page: Page, run: str) -> None:
    for _ in range(1000):
        shown = page.request.get(f"/api/runs/{run}").json()
        if shown["finished"] and shown["job"]["status"] not in ("queued", "under way"):
            return
        time.sleep(0.02)
    raise AssertionError(f"run {run} is still under way")


def _started(page: Page, configuration: int, *families: str) -> str:
    found = [
        page.request.get("/api/families", params={"name": f}).json()[0]["id"]
        for f in families
    ]
    body = {
        "configuration": configuration,
        "families": found,
        "seeds": [1],
        "score": True,
    }
    got = page.request.post("/api/runs", data=body)
    assert got.status == 202, got.json()
    run = got.json()["runs"][0]["run"]
    _ = page.goto(f"/runs/{run}")
    return run


def _weights(page: Page, name: str) -> str:
    query: dict[str, str | float | bool] = {"kind": "model", "name": name}
    [found] = page.request.get("/api/threads", params=query).json()
    return found["head"]["digest"]


@pytest.fixture
def built() -> Path:
    found = settings.portal_assets()
    if not Assets(found).built:
        pytest.fail(f"nothing built in {found}: pnpm --dir frontend build")
    return found


# Accommodating for a browser, which keeps the __Host- session cookie over plain HTTP
# only on localhost.
@pytest.fixture
def portal(served: FastAPI) -> Iterator[str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = int(s.getsockname()[1])
    server = uvicorn.Server(
        uvicorn.Config(served, host="127.0.0.1", port=port, log_level="warning")
    )
    running = threading.Thread(target=server.run, daemon=True)
    running.start()
    while not server.started:
        time.sleep(0.01)
    yield f"http://localhost:{port}"
    server.should_exit = True
    running.join(5)


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch(executable_path=settings.chromium())
        except Error as e:
            pytest.fail(f"no browser for Playwright: {e.message.splitlines()[0]}")
        yield launched
        launched.close()


@pytest.fixture
def page(browser: Browser, portal: str, alice: Person) -> Iterator[Page]:
    assert alice.login == "alice"
    context = browser.new_context(base_url=portal)
    opened = context.new_page()
    opened.set_default_timeout(15_000)
    _ = opened.goto("/sign-in")
    opened.fill('input[name="login"]', "alice")
    opened.fill('input[name="password"]', PASSWORD)
    opened.click("button:has-text('Sign in')")
    opened.wait_for_url(portal + "/")
    yield opened
    context.close()


def test_a_variation_is_run_watched_halted_scored_again_and_run_again(
    page: Page,
    world: Inventory,
    conn: Connection,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "name": LINES,
        "owner": "alice",
    }
    lines = page.request.get("/api/threads", params=query).json()[0]

    with faked(world, Store(conn).get, delay=0.3):
        run = _started(page, lines["id"], "crlf")

        expect(page.get_by_role("heading", name="Under way")).to_be_visible()
        expect(
            page.get_by_text(re.compile(r"(thinking|writing), \d+ tokens"))
        ).to_be_visible()
        page.get_by_role("button", name="Halt").click()
        expect(page.get_by_role("heading", name="Items")).to_be_visible()
        expect(page.get_by_text("Left to score by")).to_be_visible()

    with faked(world, Store(conn).get):
        page.get_by_role("button", name="Score again").click()
        expect(page.get_by_role("heading", name="Items")).to_be_visible()
        expect(page.get_by_text("Left to score by")).to_have_count(0)

        page.get_by_role("button", name="Run again").click()
        page.wait_for_url(re.compile(r"/runs/[0-9a-f-]{36}$"))
        assert page.url.rsplit("/", 1)[1] != run
        expect(page.get_by_role("heading", name="Items")).to_be_visible()
        expect(page.get_by_text("completed").first).to_be_visible()

    assert errors == []


def test_a_judge_s_configuration_is_written_in_compose(page: Page) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "purpose": "judge",
        "name": JUDGE,
    }
    judge = page.request.get("/api/threads", params=query).json()[0]
    _ = page.goto(f"/compose/{judge['id']}")
    expect(page.get_by_role("region", name="Its texts")).to_be_visible()
    expect(page.get_by_role("button", name="Save")).to_be_visible()
    expect(page.get_by_role("button", name="Run it")).to_have_count(0)
    expect(page.get_by_role("button", name="Run", exact=True)).to_have_count(0)
    assert errors == []


def test_a_configuration_s_parts_are_written_in_compose_and_saved_with_it(
    page: Page,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "name": LINES_GUIDED,
        "owner": "alice",
    }
    guided = page.request.get("/api/threads", params=query).json()[0]
    _ = page.goto(f"/compose/{guided['id']}")

    text = page.get_by_label("instructions, text 1")
    old = text.input_value()
    new = old.replace("Read the case", "Read the case closely")
    with page.expect_response(re.compile(r"/drafts$")):
        text.fill(new)

    page.get_by_role("button", name=re.compile(r"^Swedish \d+\D")).click()
    expect(page.get_by_label(f"Into Swedish: {old}", exact=True)).to_have_count(0)
    carried = page.get_by_label(f"Into Swedish: {new}", exact=True)
    expect(carried).to_have_value(re.compile(r"^Du bistår"))
    expect(page.get_by_text("Carried over from the text as it was.")).to_be_visible()
    expect(page.get_by_label("temperature", exact=True)).to_have_count(0)

    page.locator("main").get_by_role("button", name="English", exact=True).click()
    with page.expect_response(re.compile(r"/drafts$")):
        page.get_by_label("temperature", exact=True).fill("0.5")
    page.get_by_role("button", name="Save").click()
    page.wait_for_url(re.compile(rf"/compose/{guided['id']}"))
    expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()

    recipe = page.request.get(f"/api/threads/{guided['id']}").json()["recipe"]
    held = page.request.get(f"/api/components/{recipe['instructions']}").json()
    assert held["body"]["text"][0] == new
    sampling = page.request.get(f"/api/components/{recipe['sampling']}").json()
    assert sampling["body"]["temperature"] == 0.5
    into = page.request.get(f"/api/components/{recipe['translations']}").json()
    assert into["body"]["into"]["sv"][new].startswith("Du bistår")
    assert errors == []


def test_a_configuration_s_baseline_is_run_from_compose_once_it_is_saved(
    page: Page, world: Inventory, conn: Connection
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "name": LINES_GUIDED,
        "owner": "alice",
    }
    guided = page.request.get("/api/threads", params=query).json()[0]
    with faked(world, Store(conn).get, delay=0.3):
        _ = page.goto(f"/compose/{guided['id']}")
        expect(page.get_by_role("button", name="Run", exact=True)).to_be_enabled()
        with page.expect_response(re.compile(r"/drafts$")):
            page.get_by_label("temperature", exact=True).fill("0.5")
        run = page.get_by_role("button", name="Run", exact=True)
        with page.expect_navigation(timeout=120_000):
            run.click(no_wait_after=True)
        expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()
        recipe = page.request.get(f"/api/threads/{guided['id']}").json()["recipe"]
        sampling = page.request.get(f"/api/components/{recipe['sampling']}").json()
        assert sampling["body"]["temperature"] == 0.5
        runs = [
            r
            for r in page.request.get("/api/runs", params={"limit": 200}).json()
            if r["ran"]["configuration"] == guided["id"]
        ]
        assert runs and {len(r["seeds"]) for r in runs} == {1}
        saving = page.get_by_role("region", name="Saving it")
        under_way = saving.get_by_role("status")
        expect(under_way).to_contain_text("under way")
        for r in runs:
            expect(under_way.get_by_role("link", name=r["id"][:8])).to_be_visible()
        expect(run).to_be_disabled()
        for r in runs:
            assert page.request.post(f"/api/runs/{r['id']}/halt").status in (204, 409)
        expect(under_way).to_have_count(0, timeout=30_000)
        expect(run).to_be_enabled()
        fared = page.get_by_role("region", name="Baseline", exact=True)
        fared.scroll_into_view_if_needed()
        expect(fared.get_by_role("status")).to_have_count(0, timeout=30_000)
    assert errors == []


def test_a_configuration_is_run_from_compose_on_the_cases_a_tag_picks(
    page: Page, world: Inventory, conn: Connection
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "name": LINES_GUIDED,
        "owner": "alice",
    }
    guided = page.request.get("/api/threads", params=query).json()[0]
    tagged = page.request.get("/api/families", params={"tag": "targets"}).json()
    with faked(world, Store(conn).get, delay=0.3):
        _ = page.goto(f"/compose/{guided['id']}")
        picker = page.get_by_role("region", name="Run it on cases")
        picker.get_by_role("button", name=re.compile(r"^targets \d+$")).click()
        expect(picker.get_by_text(f"{len(tagged)} cases picked")).to_be_visible()
        picker.get_by_label("Replicates").fill("2")
        with page.expect_navigation(url=re.compile(r"/runs/"), timeout=120_000):
            picker.get_by_role("button", name=f"Run it on {len(tagged)} cases").click()
        runs = [
            r
            for r in page.request.get("/api/runs", params={"limit": 200}).json()
            if r["ran"]["configuration"] == guided["id"]
        ]
        assert runs and {len(r["seeds"]) for r in runs} == {2}
        for r in runs:
            assert page.request.post(f"/api/runs/{r['id']}/halt").status in (204, 409)
    assert errors == []


def test_an_earlier_version_saved_is_brought_back_as_the_latest(page: Page) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "name": LINES_GUIDED,
        "owner": "alice",
    }
    guided = page.request.get("/api/threads", params=query).json()[0]
    first = guided["head"]["id"]
    compose = f"/compose/{guided['id']}"

    def sampled() -> float:
        recipe = page.request.get(f"/api/threads/{guided['id']}").json()["recipe"]
        held = page.request.get(f"/api/components/{recipe['sampling']}").json()
        return held["body"]["temperature"]

    was = sampled()
    _ = page.goto(compose)
    with page.expect_response(re.compile(r"/drafts$")):
        page.get_by_label("temperature", exact=True).fill("0.5")
    save = page.get_by_role("button", name="Save", exact=True)
    with page.expect_navigation():
        save.click()
    expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()
    assert sampled() == 0.5

    _ = page.goto(f"{compose}?head={first}")
    expect(
        page.get_by_text("Brings version 1 of this configuration back as the latest.")
    ).to_be_visible()
    with page.expect_navigation():
        save.click()
    page.wait_for_url(re.compile(rf"/compose/{guided['id']}$"))
    expect(page.get_by_text("Version 1 of 2", exact=True)).to_be_visible()
    assert sampled() == was
    edits = page.request.get(f"/api/threads/{guided['id']}/edits").json()
    assert [e["version"] for e in edits][-3:] == [1, 2, 1]
    assert len(page.request.get("/api/threads", params=query).json()) == 1
    assert errors == []


def test_what_a_configuration_sends_slides_in_marked_against_what_was_saved(
    page: Page,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "name": LINES_GUIDED,
        "owner": "alice",
    }
    guided = page.request.get("/api/threads", params=query).json()[0]
    page.set_viewport_size({"width": 1600, "height": 1000})
    _ = page.goto(f"/compose/{guided['id']}")
    sends = page.get_by_role("region", name="What it sends")
    expect(sends).to_be_hidden()
    with page.expect_response(re.compile(r"/previews$")):
        page.get_by_role("button", name="What it sends").click()
    expect(page.locator("[data-compose]")).to_have_attribute("data-slid", "")
    shown = sends.locator("[data-preview]")
    expect(shown).to_contain_text("You are assisting")
    update = sends.get_by_role("button", name="Update")
    expect(update).to_be_disabled()
    expect(shown).to_contain_text("‹appendix 2›")
    expect(shown.locator("ins, del")).to_have_count(0)

    with page.expect_response(re.compile(r"/drafts$")):
        page.get_by_label("instructions, text 1").fill("Be brief.")
    expect(update).to_be_enabled()
    with page.expect_response(re.compile(r"/previews$")):
        update.click()
    expect(shown.locator("del").first).to_contain_text("You")
    expect(shown.locator("ins").first).to_contain_text("brief")
    with page.expect_response(re.compile(r"/previews$")):
        page.get_by_role("button", name=re.compile(r"^Swedish \d+\D")).click()
    expect(update).to_be_disabled()
    expect(shown.locator("ins, del")).to_have_count(0)
    page.get_by_label("Into Swedish: Be brief.", exact=True).fill("")
    expect(update).to_be_enabled()
    with page.expect_response(re.compile(r"/previews$")):
        update.click()
    expect(shown.get_by_title("instructions, not yet translated").first).to_be_visible()
    expect(shown.locator("del").first).to_contain_text("Du")
    expect(update).to_be_disabled()
    sends.get_by_role("button", name="As sent").click()
    expect(shown.locator("pre")).to_contain_text('"messages"')
    expect(shown.locator("pre")).not_to_contain_text("\\n")
    expect(shown.locator("pre ins").first).to_contain_text("Be brief.")
    sends.get_by_role("button", name="Close").click()
    expect(page.locator("[data-compose]")).not_to_have_attribute("data-slid", "")
    expect(page.get_by_role("button", name="What it sends")).to_be_visible()
    assert errors == []


def test_a_configuration_s_settings_are_written_by_what_they_decide(
    page: Page,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "name": "reasoned",
        "owner": "alice",
    }
    reasoned = page.request.get("/api/threads", params=query).json()[0]
    _ = page.goto(f"/compose/{reasoned['id']}")
    settings = page.get_by_role("region", name="Its settings")
    expect(settings.get_by_text("Lands at on.")).to_be_visible()
    expect(settings.get_by_label("temperature", exact=True)).to_have_attribute(
        "placeholder", "0.6"
    )
    with page.expect_response(re.compile(r"/drafts$")):
        settings.get_by_label("By hand").check()
    expect(settings.get_by_text("Effort")).to_be_visible()
    with page.expect_response(re.compile(r"/drafts$")):
        settings.get_by_label("A tool call").check()
    expect(settings.get_by_label("The answer's schema")).to_be_visible()
    expect(settings.get_by_text("The answer tool's name")).to_be_visible()

    expect(settings.get_by_text("Thinking token budget")).to_be_visible()
    model = settings.get_by_label("model", exact=True)
    gpt = model.locator("option", has_text="gpt-oss").first.get_attribute("value")
    assert gpt is not None
    _ = model.select_option(gpt)
    expect(settings.get_by_text("Thinking token budget")).to_have_count(0)

    page.get_by_label("Name", exact=True).fill("reasoned anew")
    alone = page.get_by_role("checkbox", name=re.compile("Independent of this one"))
    expect(alone).not_to_be_checked()
    alone.check()
    expect(page.get_by_text("independent of this one.")).to_be_visible()
    assert errors == []


def test_a_clinician_s_appendix_case_and_expectation_are_written_and_counted(
    page: Page,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    crlf = page.request.get("/api/families", params={"name": "crlf"}).json()[0]
    [expected] = page.request.get(f"/api/families/{crlf['id']}").json()["cases"][0][
        "expectations"
    ]
    query: dict[str, str | float | bool] = {"kind": "expectation", "owner": "alice"}
    mine = next(
        t
        for t in page.request.get("/api/threads", params=query).json()
        if t["head"]["digest"] == expected["expectation"]
    )
    query = {"kind": "configuration", "name": LINES, "owner": "alice"}
    lines = page.request.get("/api/threads", params=query).json()[0]

    def missing() -> set[tuple[str, str]]:
        look = page.request.get(f"/api/threads/{lines['id']}/variation").json()
        return {
            (r["name"], r["label"]) for r in look["reach"] if crlf["id"] in r["missing"]
        }

    held = missing()
    deleted = {"deleted": True}
    path = f"/api/threads/{mine['id']}"
    assert page.request.patch(path, data=deleted).status == 200
    gone = missing()
    assert held < gone
    _ = page.goto(f"/review/{crlf['id']}")
    saving = page.get_by_role("group", name="Saving").get_by_role("button", name="Save")
    page.get_by_role("button", name="Add an appendix").click()
    adding = page.locator("#review-appendices")
    expect(saving).to_be_disabled()
    adding.get_by_label("Name").fill("ultrasound")
    expect(saving).to_be_disabled()
    text = adding.get_by_label("Text, as it is added to the vignette")
    text.fill("Gallstones on ultrasound.")
    saving.click()
    page.wait_for_url(re.compile(r"[?&]case=sha256"))
    _ = page.goto("/library?kind=case")
    page.get_by_role("link", name="crlf", exact=True).click()
    expect(page.get_by_text("appendices: ultrasound")).to_be_visible()
    expect(page.get_by_role("link", name="write yours")).to_have_count(2)

    page.get_by_role("link", name="write yours").first.click()
    page.get_by_label("name", exact=True).fill("mine again")
    page.get_by_role("button", name="Write it as JSON").click()
    page.get_by_label("data", exact=True).fill(json.dumps(expected["data"]))
    page.get_by_role("button", name="Write it").click()
    page.wait_for_url(re.compile(r"/threads/\d+$"))
    expect(page.get_by_role("button", name="Save it")).to_be_visible()

    written_now = missing()
    assert held <= written_now < gone
    assert errors == []


def test_a_clinician_reviews_a_case_writing_what_is_expected_and_its_appendices(
    page: Page,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    noted = page.request.get("/api/families", params={"name": "noted"}).json()[0]
    vignette = page.request.get(f"/api/families/{noted['id']}/vignette").json()

    _ = page.goto(f"/review/{noted['id']}")
    first = vignette["text"].strip().splitlines()[0]
    expect(page.locator("#review-vignette")).to_contain_text(first)
    page.set_viewport_size({"width": 1440, "height": 900})
    expect(page.locator("details[data-drawer]")).to_have_count(0)
    expect(page.get_by_role("region", name="Cases")).to_be_visible()
    below = (
        "document.querySelector('#review-faring > .pane').getBoundingClientRect().top"
    )
    assert page.evaluate(below) == 900
    page.set_viewport_size({"width": 1440, "height": 360})
    assert page.evaluate(below) == 360
    page.set_viewport_size({"width": 1440, "height": 900})
    expected = page.locator("#review-expected")

    def section(name: str) -> Locator:
        return expected.locator("details").filter(
            has=page.get_by_text(name, exact=True)
        )

    expect(page.get_by_role("region", name="Expectation")).to_be_visible()
    expect(expected.locator("details[open]")).to_have_count(0)
    expect(expected.get_by_label("Name")).to_have_count(0)
    expect(section("Final diagnosis").locator("summary")).to_contain_text(
        "sepsis | septic & shock"
    )
    expect(expected.get_by_role("button", name=re.compile(r"^\+"))).to_have_count(0)
    expect(
        expected.get_by_role("button", name=re.compile(r"^Leave out"))
    ).to_have_count(0)
    statement = section("Statement")
    statement.locator("summary").first.click()
    carol = statement.locator("details").filter(has_text="Statement by carol")
    expect(carol.get_by_text(re.compile(r"^Chock, troligen septisk\."))).to_be_hidden()
    carol.locator("summary").click()
    expect(carol.get_by_text(re.compile(r"^Chock, troligen septisk\."))).to_be_visible()
    expect(carol.get_by_role("textbox")).to_have_count(0)
    expect(expected.get_by_text("Statement 1")).to_have_count(0)
    expect(statement.get_by_label("author")).to_have_count(0)
    expect(page.get_by_role("list", name="What reads notes")).to_have_count(0)
    expect(page.get_by_role("button", name=re.compile(r"^Compose"))).to_have_count(0)
    saving = page.get_by_role("group", name="Saving").get_by_role("button", name="Save")
    expect(saving).to_be_disabled()
    expect(expected.get_by_role("navigation", name="Versions")).to_have_count(0)
    expect(expected.get_by_text("Nothing to say of it.")).to_have_count(0)
    statement.get_by_label("comment").fill("Septisk chock: odla, ge antibiotika.")
    section("Final diagnosis").locator("summary").click()
    page.get_by_label("Match", exact=True).first.fill("septic & (shock")
    diagnosis = section("Final diagnosis")
    expect(diagnosis.get_by_text("is never closed")).to_be_visible()
    expect(saving).to_be_disabled()
    unread = diagnosis.get_by_role("img", name="Not as a scorer reads it")
    expect(unread).to_be_hidden()
    diagnosis.locator("summary").click()
    expect(unread).to_be_visible()
    diagnosis.locator("summary").click()
    page.get_by_label("Match", exact=True).first.fill("septic & shock")
    expect(expected.get_by_text("is never closed")).to_have_count(0)
    expect(unread).to_have_count(0)
    warning = section("Possible warnings")
    warning.locator("summary").click()
    expect(warning.get_by_label("Match", exact=True)).to_be_visible()
    warning.get_by_label("none expected").check()
    expect(warning.get_by_label("Match", exact=True)).to_have_count(0)
    saving.click()
    expect(expected.get_by_text("Version 2 of 2", exact=True)).to_be_visible()
    expect(page.get_by_text("what each changed")).to_have_count(0)
    expect(warning.locator("summary")).to_contain_text("none expected")

    expect(expected.get_by_role("button", name="Restore")).to_have_count(0)
    expect(saving).to_be_disabled()
    expected.get_by_role("button", name="The version before").click()
    expect(page.get_by_text("Save makes it the latest.")).to_be_visible()
    expect(warning.get_by_label("none expected")).not_to_be_checked()
    expect(saving).to_be_enabled()
    warning.locator("summary").click()
    warning.get_by_label("none expected").check()
    replacing: list[str] = []

    def answered(dialog: Dialog, accept: bool) -> None:
        replacing.append(dialog.message)
        _ = dialog.accept() if accept else dialog.dismiss()

    page.once("dialog", lambda d: answered(d, False))
    expected.get_by_role("button", name="The version after").click()
    expect(expected.get_by_text("Version 1 of 2", exact=True)).to_be_visible()
    expect(warning.get_by_label("none expected")).to_be_checked()
    page.once("dialog", lambda d: answered(d, True))
    expected.get_by_role("button", name="The version after").click()
    expect(expected.get_by_text("Version 2 of 2", exact=True)).to_be_visible()
    assert replacing == ["Replace what you changed with version 2?"] * 2
    expected.get_by_role("button", name="The version before").click()
    expect(expected.get_by_text("Version 1 of 2", exact=True)).to_be_visible()
    assert len(replacing) == 2
    saved = page.url
    saving.click()
    expect(expected.get_by_text("Version 3 of 3", exact=True)).to_be_visible()
    assert page.url == saved
    expect(page.get_by_label("Match", exact=True).first).not_to_have_value(
        "septic & shock"
    )
    expect(warning.get_by_label("none expected")).not_to_be_checked()
    statement.locator("summary").first.click()
    statement.get_by_label("comment").fill("Septisk chock: odla, ge antibiotika.")
    section("Final diagnosis").locator("summary").click()
    page.get_by_label("Match", exact=True).first.fill("septic & shock")
    saving.click()
    expect(expected.get_by_text("Version 4 of 4", exact=True)).to_be_visible()
    expect(statement.get_by_label("comment")).to_have_value(
        "Septisk chock: odla, ge antibiotika."
    )
    expect(page.get_by_label("Match", exact=True).first).to_have_value("septic & shock")
    statement.locator("summary").first.click()
    statement.get_by_label("comment").fill("Odla.")
    leaving: list[str] = []

    def stayed(dialog: Dialog) -> None:
        leaving.append(dialog.type)
        dialog.dismiss()

    page.once("dialog", stayed)
    _ = page.evaluate("location.reload()")
    expect(statement.get_by_label("comment")).to_have_value("Odla.")
    assert leaving == ["beforeunload"]
    statement.get_by_label("comment").fill("Septisk chock: odla, ge antibiotika.")
    expect(saving).to_be_disabled()

    page.get_by_role("button", name="Add an appendix").click()
    adding = page.locator("#review-appendices")
    adding.get_by_label("Name").fill("ultrasound")
    adding.get_by_label("Text, as it is added to the vignette").fill("Free fluid.")
    saving.click()
    page.wait_for_url(re.compile(r"[?&]case=sha256"))
    appendices = page.locator("#review-appendices")
    appendix = appendices.get_by_role("article").filter(has_text="ultrasound")
    expect(appendix).to_contain_text("Free fluid.")
    expect(appendices.get_by_role("textbox")).to_have_count(0)
    expect(page.get_by_text("a new thread of your own")).to_have_count(0)
    expect(page.get_by_label("Match", exact=True).first).to_have_value("septic & shock")
    tree = page.get_by_role("navigation", name="Cases")
    branch = tree.get_by_role("link", name="ultrasound")
    expect(branch).to_have_attribute("aria-current", "page")

    built = page.url
    bar = page.get_by_role("group", name="Saving")
    restoring = bar.get_by_role("button", name="Restore")
    appendix.get_by_role("button", name="Change it").click()
    expect(page.get_by_role("button", name="Add an appendix")).to_have_count(0)
    expect(appendices.get_by_label("Name")).to_have_value("ultrasound")
    text = appendices.get_by_label("Text, as it is added to the vignette")
    expect(text).to_have_value("Free fluid.")
    text.fill("Free fluid in Morison's pouch.")
    page.once("dialog", lambda d: d.dismiss())
    restoring.click()
    expect(text).to_have_value("Free fluid in Morison's pouch.")
    confirmed: list[str] = []

    def restored(dialog: Dialog) -> None:
        confirmed.append(dialog.type)
        dialog.accept()

    page.on("dialog", restored)
    restoring.click()
    expect(appendix).to_contain_text("Free fluid.")
    expect(appendices.get_by_role("textbox")).to_have_count(0)
    assert (page.url, confirmed) == (built, ["confirm"])
    page.remove_listener("dialog", restored)

    appendix.get_by_role("button", name="Change it").click()
    appendices.get_by_label("Name").fill("FAST")
    text.fill("Free fluid in Morison's pouch.")
    saving.click()
    page.wait_for_url(lambda url: url != built)
    appendix = appendices.get_by_role("article").filter(has_text="FAST")
    expect(appendix).to_contain_text("Free fluid in Morison's pouch.")
    branch = tree.get_by_role("link", name="FAST")
    expect(branch).to_have_attribute("aria-current", "page")
    expect(tree.get_by_role("link", name="ultrasound")).to_have_count(0)

    edited = page.url
    deleting = bar.get_by_role("button", name="Delete")
    page.once("dialog", lambda d: d.dismiss())
    deleting.click()
    expect(branch).to_have_attribute("aria-current", "page")
    assert page.url == edited
    asked: list[str] = []

    def accepted(dialog: Dialog) -> None:
        asked.append(dialog.message)
        dialog.accept()

    page.once("dialog", accepted)
    deleting.click()
    page.wait_for_url(lambda url: url != edited)
    assert asked == [
        "Delete the appendix FAST? This case and those under it leave the list."
    ]
    expect(page.get_by_role("article")).to_have_count(0)
    expect(branch).to_have_count(0)
    expect(page.get_by_role("button", name="Delete")).to_have_count(0)

    shown = page.url
    page.locator("body").press("j")
    page.wait_for_timeout(300)
    assert page.url == shown
    assert errors == []


def test_the_cases_are_filtered_in_place_by_tags_and_languages(page: Page) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    every = page.request.get("/api/families").json()
    noted = next(f for f in every if f["name"] == "noted")
    targets = [f for f in every if "targets" in f["tags"]]
    both = [f for f in targets if "swedish" in f["tags"]]
    spoken = [f for f in targets if f["language"] == "sv"]

    _ = page.goto(f"/review/{noted['id']}")
    _ = page.evaluate("window.stayed = true")
    cases = page.get_by_role("region", name="Cases")
    filters = cases.get_by_role("navigation", name="Filters")
    shown = cases.locator("li[data-tags]:visible")
    expect(shown).to_have_count(len(every))
    expect(cases.locator('[title="In sync"]').first).to_be_attached()
    filters.get_by_role("link", name="targets", exact=True).click()
    expect(shown).to_have_count(len(targets))
    filters.get_by_role("link", name="swedish", exact=True).click()
    expect(shown).to_have_count(len(both))
    assert "tag=targets" in page.url and "tag=swedish" in page.url
    first = shown.first.locator("a").first
    expect(first).to_have_attribute("href", re.compile(r"tag=targets&tag=swedish$"))
    filters.get_by_role("link", name="swedish", exact=True).click()
    filters.get_by_role("link", name="Swedish", exact=True).click()
    expect(shown).to_have_count(len(spoken))
    filters.get_by_role("link", name="all", exact=True).click()
    expect(shown).to_have_count(len(every))
    assert page.evaluate("window.stayed") is True
    assert "tag=" not in page.url and "language=" not in page.url
    assert errors == []


def test_a_case_s_tags_and_language_are_saved_with_the_page(page: Page) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    noted = page.request.get("/api/families", params={"name": "noted"}).json()[0]
    path = f"/api/families/{noted['id']}"

    _ = page.goto(f"/review/{noted['id']}")
    case = page.get_by_role("region", name="The case")
    expect(case.get_by_role("link", name="Show in the Library")).to_be_visible()
    bar = page.get_by_role("group", name="Saving")
    saving = bar.get_by_role("button", name="Save")
    restoring = bar.get_by_role("button", name="Restore")
    expect(saving).to_be_disabled()
    expect(restoring).to_be_disabled()
    tag = bar.get_by_label("A new tag")
    tag.fill("stray")
    tag.press("Enter")
    expect(bar.get_by_role("button", name="Take away the tag stray")).to_be_visible()
    agreed_to: list[str] = []

    def agreed(dialog: Dialog) -> None:
        agreed_to.append(dialog.type)
        dialog.accept()

    page.on("dialog", agreed)
    restoring.click()
    expect(bar.get_by_role("button", name="Take away the tag stray")).to_have_count(0)
    expect(restoring).to_be_disabled()
    assert agreed_to == ["confirm"]
    page.remove_listener("dialog", agreed)
    assert "stray" not in page.request.get(path).json()["tags"]
    tag.fill("reviewed")
    tag.press("Enter")
    bar.get_by_role("button", name="Change its language").click()
    _ = bar.get_by_label("Its language").select_option("sv")
    expect(bar).to_contain_text("Swedish")
    held = page.request.get(path).json()
    assert "reviewed" not in held["tags"] and held["language"] != "sv"
    with page.expect_navigation():
        saving.click()
    held = page.request.get(path).json()
    assert "reviewed" in held["tags"] and held["language"] == "sv"
    expect(bar).to_contain_text("Swedish")
    expect(saving).to_be_disabled()

    bar.get_by_role("button", name="Take away the tag reviewed").click()
    with page.expect_navigation():
        saving.click()
    assert "reviewed" not in page.request.get(path).json()["tags"]
    assert errors == []


def test_a_case_with_none_of_one_s_own_shows_the_shared_one_and_waits_for_typing(
    page: Page,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    crlf = page.request.get("/api/families", params={"name": "crlf"}).json()[0]
    [expected] = page.request.get(f"/api/families/{crlf['id']}").json()["cases"][0][
        "expectations"
    ]
    query: dict[str, str | float | bool] = {"kind": "expectation", "owner": "alice"}
    mine = next(
        t
        for t in page.request.get("/api/threads", params=query).json()
        if t["head"]["digest"] == expected["expectation"]
    )
    path = f"/api/threads/{mine['id']}"
    assert page.request.patch(path, data={"deleted": True}).status == 200

    with page.expect_response(lambda r: r.url.endswith("/api/components/check")):
        _ = page.goto(f"/review/{crlf['id']}")
    saving = page.get_by_role("group", name="Saving").get_by_role("button", name="Save")
    expect(saving).to_be_disabled()
    pattern = expected["data"]["diagnosis"]["pattern"]
    expect(page.locator("[data-offered]")).to_contain_text(pattern)
    expect(page.get_by_text("a new thread of your own")).to_have_count(0)
    expect(page.get_by_text("Nothing to say of it.")).to_have_count(0)
    expect(page.get_by_text("expectation.invalid")).to_have_count(0)
    page.locator("#review-expected summary").filter(has_text="Final diagnosis").click()
    with page.expect_response(lambda r: r.url.endswith("/api/components/check")):
        page.get_by_label("Match", exact=True).first.fill(pattern)
    expect(saving).to_be_enabled()
    expect(page.get_by_text("Nothing to say of it.")).to_have_count(0)
    expect(page.get_by_text("expectation.invalid")).to_have_count(0)
    assert errors == []


def test_a_scorer_s_page_fits_a_phone(page: Page) -> None:
    query: dict[str, str | float | bool] = {"kind": "scorer", "name": LINES}
    lines = page.request.get("/api/threads", params=query).json()[0]
    page.set_viewport_size({"width": 390, "height": 844})
    _ = page.goto(f"/scoring/{lines['id']}")
    expect(page.get_by_role("heading", name="Views")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth") == 390


def test_a_judged_view_is_written_with_a_new_judge_and_scored_through_the_worker(
    page: Page,
    world: Inventory,
    conn: Connection,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    noted = page.request.get("/api/families", params={"name": "noted"}).json()[0]
    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "name": LINES,
        "owner": "alice",
    }
    lines = page.request.get("/api/threads", params=query).json()[0]
    body = {"configuration": lines["id"], "families": [noted["id"]]}
    query = {"kind": "scorer", "name": LINES}
    scorer = page.request.get("/api/threads", params=query).json()[0]
    forks = f"/api/threads/{scorer['id']}/forks"
    mine = page.request.post(forks, data={"name": "noted-judged"}).json()

    with faked(world, Store(conn).get):
        run = page.request.post("/api/runs", data=body).json()["runs"][0]["run"]
        _settled(page, run)
        _ = page.goto(f"/threads/{mine['id']}")
        page.get_by_role("button", name="+ a view").click()
        view = page.locator("li").filter(has=page.get_by_label("Its label")).last
        view.get_by_label("Its label").fill("met")
        _ = view.get_by_label("Reads of what is expected").select_option(
            label="each of notes › comment"
        )
        _ = view.get_by_role("combobox", name="Compared by").select_option("verdict")
        judge = view.get_by_role("combobox", name="Judge")
        _ = judge.select_option("new")
        written = page.get_by_role("region", name="A new judge")
        written.get_by_label("Name").fill("strict")
        _ = written.get_by_label("Asked under the model").select_option(QWEN_ARTIFACT)
        written.get_by_label("Seeds, a call each").fill("1, 2")
        written.get_by_role("button", name="Save").click()
        expect(written).to_have_count(0)
        expect(judge.locator("option:checked")).to_contain_text("strict")
        expect(view.get_by_role("combobox", name="Its verdict at")).to_have_value(
            "/meets"
        )
        page.get_by_role("button", name="Save it").click()
        expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()

        _ = page.goto(f"/runs/{run}")
        page.get_by_role("button", name="Score again").click()
        page.wait_for_url(re.compile(rf"/runs/{run}$"))
        _settled(page, run)
    _ = page.goto(f"/runs/{run}")
    expect(page.get_by_text(re.compile(r"^Left to score by"))).to_have_count(0)
    head = page.request.get(f"/api/threads/{mine['id']}").json()["head"]["digest"]
    scores = page.request.get(f"/api/runs/{run}/scores").json()
    assert head in {g["scorer"] for g in scores}
    query = {"kind": "judge", "name": "strict"}
    [strict] = page.request.get("/api/threads", params=query).json()
    held = page.request.get(f"/api/components/{strict['head']['digest']}").json()
    assert held["body"]["seeds"] == [1, 2]
    assert errors == []


def test_what_a_judge_is_asked_is_rewritten_on_its_page_and_picked_in_the_library(
    page: Page,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    query: dict[str, str | float | bool] = {"kind": "judge", "name": "verdict"}
    [archives] = page.request.get("/api/threads", params=query).json()
    query = {"kind": "scorer", "name": "judged"}
    judged = page.request.get("/api/threads", params=query).json()[0]
    was = page.request.get(f"/api/components/{judged['head']['digest']}").json()

    _ = page.goto(f"/scoring/{archives['id']}")
    page.get_by_role("button", name="Change what it is asked").click()
    panel = page.get_by_role("region", name="What its judge is asked, as you write it")
    told = panel.get_by_label("What it is told to answer, text 1")
    expect(told).to_have_value(
        "Say whether the answer meets what was expected, and why."
    )
    told.fill("Say whether the answer meets carol's note, and why.")
    preview = panel.get_by_role("list", name="As it would read")
    expect(preview).to_contain_text("meets carol's note")
    expect(preview).to_contain_text("Chock, troligen septisk.")
    panel.get_by_role("button", name="Save what it is asked").click()
    page.wait_for_url(lambda url: not url.endswith(f"/scoring/{archives['id']}"))

    query = {"kind": "judge", "name": "verdict", "owner": "alice"}
    [verdict] = page.request.get("/api/threads", params=query).json()
    assert page.url.endswith(f"/scoring/{verdict['id']}")
    asked = page.get_by_role("region", name="What it is asked", exact=True)
    expect(asked).to_contain_text("meets carol's note")
    held = page.request.get(f"/api/components/{verdict['head']['digest']}").json()
    query = {"kind": "configuration", "purpose": "judge", "owner": "alice"}
    judging = page.request.get("/api/threads", params=query).json()
    [asking] = [t for t in judging if t["name"] == "judge"]
    assert held["body"]["skeleton"] == asking["head"]["digest"]
    query = {"kind": "scorer", "name": "judged"}
    [still] = page.request.get("/api/threads", params=query).json()
    assert still["head"]["digest"] == judged["head"]["digest"]

    forks = f"/api/threads/{judged['id']}/forks"
    made = page.request.post(forks, data={"name": "judged-anew"}).json()
    _ = page.goto(f"/threads/{made['id']}")
    expect(page.get_by_text("Change what it is asked")).to_have_count(0)
    picks = page.get_by_role("combobox", name="Judge", exact=True)
    for at in range(2):
        _ = picks.nth(at).select_option(verdict["head"]["digest"])
    page.get_by_role("button", name="Save it").click()
    expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()

    made = page.request.get(f"/api/threads/{made['id']}").json()
    now = page.request.get(f"/api/components/{made['head']['digest']}").json()
    old = {v["judge"] for v in was["body"]["views"] if v["metric"] == "verdict"}
    assert len(old) == 1 and old.isdisjoint(v["judge"] for v in now["body"]["views"])
    assert [v["judge"] for v in now["body"]["views"] if v["metric"] == "verdict"] == [
        verdict["head"]["digest"]
    ] * 2
    assert errors == []


def test_a_translator_carries_an_edited_instruction_over_and_compose_takes_it(
    page: Page,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    def thread(kind: str, name: str) -> dict[str, Any]:
        query: dict[str, str | float | bool] = {
            "kind": kind,
            "name": name,
            "owner": "alice",
        }
        return page.request.get("/api/threads", params=query).json()[0]

    clinician = thread("instructions", "clinician")
    body = page.request.get(f"/api/components/{clinician['head']['digest']}").json()
    text = body["body"]["text"]
    text[0] = text[0].replace("your assessment.", "your assessment and plan.")
    changed = {"head": clinician["head"]["id"], "component": body["body"]}
    edited = page.request.post(
        f"/api/threads/{clinician['id']}/edits", data={**changed, "language": "en"}
    )
    assert edited.status == 201, edited.json()
    guided = thread("configuration", LINES_GUIDED)
    parts = {"instructions": edited.json()["digest"]}
    moved = page.request.post(
        f"/api/threads/{guided['id']}/edits",
        data={"head": guided["head"]["id"], "parts": parts},
    )
    assert moved.status == 201, moved.json()

    held: dict[str, str | float | bool] = {"kind": "translations", "owner": "alice"}
    [translations] = page.request.get("/api/threads", params=held).json()
    _ = page.goto(f"/threads/{translations['id']}?into=sv")
    expect(
        page.get_by_text(re.compile("started from the translation of a similar text"))
    ).to_be_visible()
    swedish = page.get_by_label("Its translation").first
    expect(swedish).to_have_value(
        "Du bistår en läkare på en akutmottagning. Läs fallet och ge din bedömning."
    )
    swedish.fill(
        "Du bistår en läkare på en akutmottagning. Läs fallet och ge din bedömning "
        + "och plan."
    )
    with page.expect_navigation():
        page.get_by_role("button", name="Save it").click()
    expect(page.get_by_text("Not translated yet")).to_have_count(0)

    page.locator(f'a[href^="/compose/{guided["id"]}?translations="]').click()
    page.wait_for_url(re.compile(rf"/compose/{guided['id']}\?translations="))
    expect(
        page.get_by_text(re.compile(r"^Saves version \d+ of this configuration"))
    ).to_be_visible()
    with page.expect_navigation():
        page.get_by_role("button", name="Save", exact=True).click()

    look = page.request.get(
        f"/api/threads/{guided['id']}/variation", params={"tag": "swedish"}
    ).json()
    [swedish_cases] = [c for c in look["languages"] if c["language"] == "sv"]
    assert (swedish_cases["translated"], swedish_cases["refused"]) == (True, None)
    assert errors == []


def test_a_text_an_expectation_and_a_scorer_s_views_are_written_in_their_editors(
    page: Page,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    def mine(kind: str, name: str | None = None) -> dict[str, Any]:
        query: dict[str, str | float | bool] = {"kind": kind, "owner": "alice"}
        listed = page.request.get("/api/threads", params=query).json()
        return next(t for t in listed if name in (None, t["name"]))

    def body(thread: dict[str, Any]) -> dict[str, Any]:
        head = page.request.get(f"/api/threads/{thread['id']}").json()["head"]
        return page.request.get(f"/api/components/{head['digest']}").json()["body"]

    clinician = mine("instructions", "clinician")
    _ = page.goto(f"/threads/{clinician['id']}")
    expect(page.get_by_text("‹what it is told to answer›")).to_be_visible()
    page.get_by_label("text, text 1").fill("Be brief.")
    page.get_by_role("button", name="Save it").click()
    expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()
    [text, insert] = body(clinician)["text"]
    assert (text, insert["insert"]) == ("Be brief.", "output_guidance")

    expectation = mine("expectation")
    was = body(expectation)
    _ = page.goto(f"/threads/{expectation['id']}")
    diagnosis = page.get_by_role("group", name="Final diagnosis", exact=True)
    diagnosis.get_by_label("Match", exact=True).fill("pneumonitis")
    page.get_by_role("button", name="Save it").click()
    expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()
    now = body(expectation)
    assert now["data"]["diagnosis"]["pattern"] == "pneumonitis"
    assert (now["case"], now["expectation_schema"]) == (
        was["case"],
        was["expectation_schema"],
    )

    _ = page.goto("/library/new?kind=expectation")
    expect(page.get_by_text("Pick its expectation schema first")).to_be_visible()
    _ = page.get_by_label("expectation schema", exact=True).select_option(index=1)
    expect(
        page.get_by_role("group", name="Final diagnosis", exact=True)
    ).to_be_visible()
    page.get_by_role("button", name="Write it as JSON").click()
    expect(page.get_by_label("data", exact=True)).to_be_visible()
    page.get_by_role("button", name="Back to the form").click()
    expect(
        page.get_by_role("group", name="Final diagnosis", exact=True)
    ).to_be_visible()

    query: dict[str, str | float | bool] = {"kind": "scorer", "name": "lines"}
    [lines] = page.request.get("/api/threads", params=query).json()
    forks = f"/api/threads/{lines['id']}/forks"
    scorer = page.request.post(forks, data={"name": "my lines"}).json()
    _ = page.goto(f"/threads/{scorer['id']}")
    page.get_by_role("button", name="Save it").click()
    expect(page.get_by_text("Version 1 of 1")).to_be_visible()
    edits = f"/api/threads/{scorer['id']}/edits"
    assert len(page.request.get(edits).json()) == 1
    page.get_by_label("Its label").first.fill("first")
    page.get_by_role("button", name="Save it").click()
    expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()
    assert page.request.get(edits).json()[-1]["labels"]["views"][0] == "first"
    assert body(scorer)["views"] == body(lines)["views"]
    assert errors == []


def test_few_shot_messages_and_a_contract_are_written_in_forms_and_json_checked_as_typed(
    page: Page,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    def mine(kind: str, name: str) -> dict[str, Any]:
        query: dict[str, str | float | bool] = {"kind": kind, "owner": "alice"}
        listed = page.request.get("/api/threads", params=query).json()
        return next(t for t in listed if t["name"] == name)

    def body(thread: dict[str, Any]) -> dict[str, Any]:
        head = page.request.get(f"/api/threads/{thread['id']}").json()["head"]
        return page.request.get(f"/api/components/{head['digest']}").json()["body"]

    worked = mine("few_shot", "worked-example")
    was = body(worked)["messages"]
    _ = page.goto(f"/threads/{worked['id']}")
    page.get_by_role("button", name="+ messages").click()
    added = page.get_by_role("group", name=f"messages {len(was) + 1}", exact=True)
    _ = added.get_by_label("role", exact=True).select_option(label="user")
    added.get_by_label("content", exact=True).fill("And now?")
    page.get_by_role("button", name="Save it").click()
    expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()
    assert body(worked)["messages"] == [*was, {"role": "user", "content": "And now?"}]

    native = mine("output", "native")
    _ = page.goto(f"/threads/{native['id']}")
    _ = page.get_by_label("kind", exact=True).select_option("tool")
    page.get_by_label("name", exact=True).fill("final_result")
    page.get_by_role("button", name="Save it").click()
    expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()
    assert body(native)["contract"]["kind"] == "tool"
    assert body(native)["contract"]["name"] == "final_result"

    off = mine("reasoning", "off")
    _ = page.goto(f"/threads/{off['id']}")
    kwargs = page.get_by_label("chat template kwargs", exact=True)
    kwargs.fill('{"enable_thinking": fals')
    expect(page.get_by_text("It isn't JSON yet")).to_be_visible()
    page.get_by_role("button", name="Save it").click()
    expect(page.get_by_text("Version 1 of 1")).to_be_visible()
    assert len(page.request.get(f"/api/threads/{off['id']}/edits").json()) == 1
    kwargs.fill('{"enable_thinking": false}')
    expect(page.get_by_text("It isn't JSON yet")).to_be_hidden()
    _ = page.get_by_label("level", exact=True).select_option(label="none")
    page.get_by_role("button", name="Save it").click()
    expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()
    assert body(off)["chat_template_kwargs"] == {"enable_thinking": False}
    assert errors == []


def test_a_researcher_s_chunks_are_written_in_their_forms_and_made_into_a_configuration(
    page: Page,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    def mine(kind: str, name: str) -> dict[str, Any]:
        query: dict[str, str | float | bool] = {"kind": kind, "name": name}
        listed = page.request.get("/api/threads", params={**query, "owner": "alice"})
        return listed.json()[0]

    case = mine("prompt", "case")
    _ = page.goto(f"/threads/{case['id']}")
    segments = ["The case:\n", {"slot": "vignette"}, {"slot": "appendices"}]
    page.get_by_role("button", name="Write it as JSON").click()
    page.get_by_label("segments", exact=True).fill(json.dumps(segments))
    page.get_by_role("button", name="Save it").click()
    expect(page.get_by_text("Version 2 of 2", exact=True)).to_be_visible()
    prompt = mine("prompt", "case")["head"]["digest"]
    held = page.request.get(f"/api/components/{prompt}").json()["body"]
    assert held["segments"] == [
        "The case:\n",
        {"slot": "vignette"},
        {"slot": "appendices"},
    ]

    _ = page.goto("/library?kind=sampling")
    page.get_by_role("link", name="Write a new one").click()
    page.get_by_label("temperature", exact=True).fill("0.3")
    page.get_by_label("name", exact=True).fill("warm")
    page.get_by_role("button", name="Write it").click()
    page.wait_for_url(re.compile(r"/threads/\d+$"))
    warm = mine("sampling", "warm")["head"]["digest"]
    assert (
        page.request.get(f"/api/components/{warm}").json()["body"]["temperature"] == 0.3
    )

    _ = page.goto("/library?kind=configuration")
    page.get_by_role("link", name="Write a new one").click()
    _ = page.get_by_label("prompt", exact=True).select_option(prompt)
    _ = page.get_by_label("output", exact=True).select_option(label=LINES)
    _ = page.get_by_label("sampling", exact=True).select_option(warm)
    model = _weights(page, QWEN_ARTIFACT)
    _ = page.get_by_label("model", exact=True).select_option(model)
    page.get_by_label("name", exact=True).fill("lines-warm")
    page.get_by_role("button", name="Write it").click()
    page.wait_for_url(re.compile(r"/threads/\d+$"))
    configuration = mine("configuration", "lines-warm")
    recipe = page.request.get(f"/api/threads/{configuration['id']}").json()["recipe"]
    assert (recipe["prompt"], recipe["sampling"]) == (prompt, warm)
    assert errors == []


def test_a_trial_is_begun_of_the_picked_cases_in_their_language_and_run(
    page: Page,
    world: Inventory,
    conn: Connection,
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _ = page.goto("/library?kind=case")
    page.get_by_label("pick nfd").check()
    page.get_by_label("pick svenska").check()
    page.get_by_role("button", name="Begin a trial of the picked").click()
    page.wait_for_url(re.compile(r"/library/new\?"))
    page.get_by_label("name", exact=True).fill("swedish")
    _ = page.get_by_label("skeleton").select_option(label=LINES_GUIDED)
    _ = page.get_by_label("engine").select_option(label=QWEN_ARTIFACT)
    page.get_by_role("button", name="Write it").click()
    page.wait_for_url(re.compile(r"/threads/\d+$"))
    expect(page.get_by_label("skeleton")).to_have_text(
        re.compile(f"{LINES_GUIDED}, in Swedish")
    )

    page.get_by_role("link", name="Run it").click()
    page.wait_for_url(re.compile(r"/lab/run\?"))
    page.get_by_label("Score it once it is done").uncheck()
    with faked(world, Store(conn).get):
        page.get_by_role("button", name="Run it").click()
        page.wait_for_url(re.compile(r"/runs/[0-9a-f-]{36}$"))
        expect(page.get_by_role("link", name="swedish")).to_be_visible()
    assert errors == []


# Accommodating for Chromium, which runs no script on a page while a navigation from it is held:
# the navigations a press starts are cancelled instead, which leaves the page as pressed.
def test_a_press_shows_until_the_next_page_comes_and_sends_its_form_once(
    page: Page,
) -> None:
    asked: list[str] = []
    held: list[Route] = []

    def cancelled(route: Route) -> None:
        asked.append(route.request.url)
        route.abort("aborted")

    back = "dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}))"
    stop = "setTimeout(() => document.querySelector('[value=trial]').click()); setTimeout(stop, 200)"
    new = re.compile(r"/library/new\?")
    marked = page.locator("html[data-leaving], [data-pressed], [data-sent]")
    _ = page.goto("/library?kind=case")
    page.get_by_label("pick nfd").check()
    _ = page.route(new, cancelled)
    begin = page.get_by_role("button", name="Begin a trial of the picked")
    begin.click()
    expect(begin).to_have_attribute("data-pressed", "")
    expect(page.locator("html")).to_have_attribute("data-leaving", "")
    begin.click()
    page.wait_for_timeout(100)
    assert len(asked) == 1 and "kind=trial" in asked[0]

    _ = page.evaluate(back)
    expect(marked).to_have_count(0)
    begin.click()
    expect(begin).to_have_attribute("data-pressed", "")
    page.wait_for_timeout(100)
    assert len(asked) == 2

    page.unroute(new)
    _ = page.route(new, lambda r: held.append(r))
    _ = page.evaluate(back)
    _ = page.evaluate(stop)
    page.wait_for_timeout(400)
    assert len(held) == 1
    expect(marked).to_have_count(0)
    held.pop().abort()

    _ = page.goto("/library?kind=configuration")
    _ = page.route(re.compile(r"/threads/\d+$"), cancelled)
    lines = page.get_by_role("link", name=LINES, exact=True).first
    lines.click()
    expect(lines).to_have_attribute("data-pressed", "")
    expect(page.locator("html")).to_have_attribute("data-leaving", "")


def test_the_library_s_kinds_scroll_on_their_own_beside_a_long_page(
    page: Page,
) -> None:
    page.set_viewport_size({"width": 1280, "height": 480})
    _ = page.goto("/library?kind=configuration")
    _ = page.evaluate("scrollTo(0, 600)")
    kinds = page.get_by_role("navigation", name="Kinds")
    held = kinds.locator(":scope > div").bounding_box()
    assert held is not None and held["y"] + held["height"] <= 480
    tool = kinds.get_by_role("link", name=re.compile(r"^tool\b"))
    tool.scroll_into_view_if_needed()
    expect(tool).to_be_in_viewport()
    assert page.evaluate("scrollY") == 600

    judge = kinds.get_by_role("link", name=re.compile(r"^judge\b"))
    judge.click()
    page.wait_for_url("**/library?kind=judge")
    expect(judge).to_be_in_viewport()
    assert page.evaluate("scrollY") == 0


def test_a_long_list_is_paged_found_in_and_shows_the_page_a_jump_is_to(
    page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ROWS_PER_PAGE", 2)
    query: dict[str, str | float | bool] = {"kind": "model"}
    handles = {
        h["name"]: h["id"]
        for h in page.request.get("/api/threads", params=query).json()
    }
    names = sorted(handles)
    _ = page.goto("/world")
    listed = page.locator("#handles")
    shown = listed.locator("details:visible")
    pages = listed.get_by_role("navigation", name="Pages")
    expect(shown).to_have_count(2)
    expect(pages).to_contain_text(f"page 1 of {(len(names) + 1) // 2}")
    expect(pages.get_by_role("button", name="Previous")).to_be_disabled()
    pages.get_by_role("button", name="Next").click()
    expect(pages).to_contain_text("page 2 of")
    expect(shown.first).to_have_id(f"handle-{handles[names[2]]}")

    listed.get_by_role("searchbox").fill(QWEN_BARE_ARTIFACT.upper())
    expect(shown).to_have_count(1)
    expect(listed).to_contain_text(f"1 of {len(names)}")
    expect(pages).to_be_hidden()

    last = f"handle-{handles[names[-1]]}"
    _ = page.evaluate(f"location.hash = '#{last}'")
    expect(page.locator(f"#{last}")).to_be_visible()
    expect(page.locator(f"#{last}")).to_have_attribute("open", "")
    expect(listed.get_by_role("searchbox")).to_have_value("")


def test_a_jump_to_a_card_of_the_world_opens_it(page: Page) -> None:
    query: dict[str, str | float | bool] = {"kind": "model", "name": QWEN_ARTIFACT}
    handle = page.request.get("/api/threads", params=query).json()[0]
    _ = page.goto(f"/world#handle-{handle['id']}")
    card = page.locator(f"#handle-{handle['id']}")
    expect(card).to_have_attribute("open", "")
    endpoint = page.locator(f'[id="endpoint-{QWEN}"]')
    expect(endpoint).not_to_have_attribute("open", "")
    card.locator(f'a[href="#endpoint-{QWEN}"]').click()
    expect(endpoint).to_have_attribute("open", "")
    expect(endpoint).to_be_in_viewport()


def test_a_case_over_the_limit_isn_t_sent_and_says_why(
    page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "TYPED_TEXT_LIMIT", 10)
    _ = page.goto("/")
    case = page.get_by_label("The case")
    over = page.get_by_text(re.compile(r"^A case holds at most 10 characters"))
    case.fill("chest pai\N{ANATOMICAL HEART}")
    expect(over).to_have_count(0)
    case.fill("chest pain\N{ANATOMICAL HEART}")
    expect(over).to_have_text("A case holds at most 10 characters; this one has 11.")
    expect(page.get_by_role("button", name="Analyze")).to_be_disabled()


def test_an_island_says_what_its_page_s_catalog_holds_in_the_locale_asked_for(
    page: Page, served: FastAPI, tmp_path: Path
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    served.state.locales = Locales(
        catalog(
            tmp_path,
            """
            #: frontend/src/islands/Home.svelte
            msgid "Analyze"
            msgstr "Analysera"

            #: frontend/src/islands/Home.svelte
            msgid ""
            "<span class=\\"gradient-text\\">Emergency</span> <span "
            "class=\\"text-foreground\\">Differential Diagnostics</span>"
            msgstr "<span class=\\"gradient-text\\">Akut</span> differentialdiagnostik"

            #: frontend/src/lib/variation/Texts.svelte
            msgid "Its texts"
            msgstr "Dess texter"
            """,
        )
    )
    page.set_extra_http_headers({"accept-language": "sv"})
    _ = page.goto("/")
    expect(
        page.get_by_role("heading", name="Akut differentialdiagnostik")
    ).to_be_visible()
    expect(page.get_by_role("button", name="Analysera")).to_be_visible()
    expect(page.get_by_text("Written in")).to_be_visible()

    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "name": LINES,
        "owner": "alice",
    }
    lines = page.request.get("/api/threads", params=query).json()[0]
    _ = page.goto(f"/compose/{lines['id']}")
    expect(page.get_by_role("region", name="Dess texter")).to_be_visible()
    assert errors == []


def _lines(page: Page) -> dict[str, Any]:
    query: dict[str, str | float | bool] = {"kind": "configuration", "name": LINES}
    [lines] = page.request.get(
        "/api/threads", params={**query, "owner": "alice"}
    ).json()
    return lines


@pytest.mark.parametrize("template", ["ran"], indirect=True)
def test_a_run_s_items_are_paged_and_found_in_as_they_come(
    page: Page,
    monkeypatch: pytest.MonkeyPatch,
    world: Inventory,
    conn: Connection,
) -> None:
    monkeypatch.setattr(settings, "ROWS_PER_PAGE", 1)
    with faked(world, Store(conn).get, delay=0.3):
        _ = _started(page, _lines(page)["id"], "crlf", "noted")
        live = page.locator("#run-live")
        pages = live.get_by_role("navigation", name="Pages")
        expect(pages).to_contain_text("page 1 of 2")
        expect(live.locator("details")).to_have_count(1)
        pages.get_by_role("button", name="Next").click()
        expect(pages).to_contain_text("page 2 of 2")
        live.get_by_role("searchbox").fill("NOTED")
        expect(live.locator("details")).to_have_count(1)
        expect(live.locator("details summary")).to_contain_text("noted")
        expect(live).to_contain_text("1 of 2")
        expect(pages).to_be_hidden()
        page.get_by_role("button", name="Halt").click()
        expect(page.get_by_role("heading", name="Items")).to_be_visible()


def test_a_case_is_run_from_its_review_once_what_changed_is_saved(
    page: Page, world: Inventory, conn: Connection
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    noted = page.request.get("/api/families", params={"name": "noted"}).json()[0]
    with faked(world, Store(conn).get, delay=0.3):
        _ = page.goto(f"/review/{noted['id']}")
        bar = page.get_by_role("group", name="Saving")
        bar.get_by_label("A new tag").fill("evaluated")
        bar.get_by_label("A new tag").press("Enter")
        asked: list[str] = []

        def dismissed(dialog: Dialog) -> None:
            asked.append(dialog.message)
            dialog.dismiss()

        page.on("dialog", dismissed)
        run = bar.get_by_role("button", name="Run")
        with page.expect_navigation(timeout=120_000):
            run.click(no_wait_after=True)
        assert asked == []
        expect(run).to_be_disabled()
        expect(page.locator("#evaluating")).to_have_count(0)
        family = page.request.get(f"/api/families/{noted['id']}").json()
        assert "evaluated" in family["tags"]
        runs = page.request.get(
            "/api/runs", params={"reaching": noted["case"], "limit": 200}
        ).json()
        assert len(runs) > 2
        for r in runs:
            assert page.request.post(f"/api/runs/{r['id']}/halt").status in (204, 409)
    assert errors == []


def test_a_field_is_measured_in_a_column_of_its_own_and_closed_again(
    page: Page, world: Inventory, conn: Connection
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    noted = page.request.get("/api/families", params={"name": "noted"}).json()[0]
    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "name": LINES,
        "owner": "alice",
    }
    lines = page.request.get("/api/threads", params=query).json()[0]
    body = {"configuration": lines["id"], "families": [noted["id"]]}
    page.set_viewport_size({"width": 1440, "height": 900})
    with faked(world, Store(conn).get):
        run = page.request.post("/api/runs", data=body).json()["runs"][0]["run"]
        _settled(page, run)
    _ = page.goto(f"/review/{noted['id']}")
    review = page.locator("[data-review]")
    measuring = page.get_by_role("region", name="Measuring the expectation")
    diagnosis = page.locator('details[data-field="diagnosis"]')
    warning = page.locator('details[data-field="warning"]')
    expect(measuring).to_be_hidden()
    diagnosis.get_by_role("button", name="Measure").click()
    expect(page).to_have_url(re.compile(r"[?&]measure=diagnosis"))
    expect(review).to_have_attribute("data-slid", "")
    expect(diagnosis).to_have_attribute("open", "")
    expect(warning).to_have_attribute("inert", "")
    expect(
        page.locator("details[data-field] button", has_text="Measure")
    ).to_have_count(0)
    measured = measuring.locator("[data-measured]")
    expect(measured).to_contain_text("1 answers", timeout=30_000)
    expect(measured.locator("> ol > li").first).to_be_visible()
    found = measuring.get_by_role("button", name=re.compile(r"^Found"))

    diagnosis.get_by_label("Match").fill("nothing & like & it")
    measuring.get_by_role("button", name="Update").click()
    expect(found).to_contain_text("0")
    expect(measured.locator("mark")).to_have_count(0)
    measuring.get_by_role("button", name="Close").click()
    expect(review).not_to_have_attribute("data-slid", "")
    expect(page).not_to_have_url(re.compile(r"measure="))
    expect(warning).not_to_have_attribute("inert", "")
    _ = page.go_back()
    expect(review).to_have_attribute("data-slid", "")
    assert errors == []


def test_how_a_case_fares_is_drawn_below_its_review_once_scrolled_to(
    page: Page, world: Inventory, conn: Connection
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    noted = page.request.get("/api/families", params={"name": "noted"}).json()[0]
    query: dict[str, str | float | bool] = {
        "kind": "configuration",
        "name": LINES,
        "owner": "alice",
    }
    lines = page.request.get("/api/threads", params=query).json()[0]
    body = {"configuration": lines["id"], "families": [noted["id"]]}
    page.set_viewport_size({"width": 1440, "height": 900})
    with faked(world, Store(conn).get):
        run = page.request.post("/api/runs", data=body).json()["runs"][0]["run"]
        _settled(page, run)
    _ = page.goto(f"/review/{noted['id']}")
    faring = page.get_by_role("region", name="How the case fares")
    expect(faring.get_by_role("figure").first).to_have_count(0)
    faring.scroll_into_view_if_needed()
    expect(faring.get_by_role("figure").first).to_be_visible(timeout=30_000)
    strip = faring.get_by_role("img", name=re.compile(rf"^{LINES}: \d\.\d\d, above"))
    expect(strip.first).to_be_visible()
    expect(
        faring.get_by_role("link", name=re.compile(r"^\d\.\d\d$")).first
    ).to_have_attribute("href", re.compile(r"^/scores/"))
    expect(faring.get_by_text("Other cases, drawn")).to_have_count(0)
    standing = faring.get_by_role("list", name="Where each configuration stands")
    expect(
        standing.get_by_role("listitem").filter(has_text=LINES).first
    ).to_contain_text("aren't three replicates and a repeat")
    expect(strip.first).to_have_accessible_name(re.compile(r"not as things are now$"))
    expect(
        faring.get_by_role("link", name=re.compile(r"^Replicate 1: \d\.\d\d$")).first
    ).to_have_attribute("href", re.compile(r"^/scores/"))
    expect(page.get_by_role("button", name="Run", exact=True)).to_be_enabled()
    assert errors == []


def test_a_landing_page_s_picture_opens_over_it_and_a_click_beside_it_closes_it(
    browser: Browser, portal: str
) -> None:
    context = browser.new_context(base_url=portal)
    page = context.new_page()
    _ = page.goto("/")
    enlarged = page.locator("#enlarged")
    page.locator("a[data-enlarge]").first.click()
    expect(enlarged).to_have_attribute("open", "")
    enlarged.locator("img").click()
    expect(enlarged).to_have_attribute("open", "")
    page.mouse.click(5, 5)
    expect(enlarged).not_to_have_attribute("open", "")
    assert page.url == portal + "/"
    context.close()
