import json
import re

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

from chatddx import settings
from chatddx.api.test.helpers import family, thread
from chatddx.factors.base import resolve
from chatddx.factors.engine import FileDigest, LocalModel
from chatddx.factors.request import CHUNK_PARTS, RECIPE_PARTS
from chatddx.factors.scoring import Scorer
from chatddx.identity import Person
from chatddx.locale import upfirst
from chatddx.portal.shelves import SHELVES
from chatddx.portal.test.helpers import said, shown, submitted
from chatddx.store import Catalog, Store
from chatddx.store.store import Connection
from chatddx.test.world import (
    GPT_OSS_ARTIFACT,
    JUDGE,
    LINES,
    MISTRAL_ARTIFACT,
    NATIVE,
    OFF,
    QWEN_ARTIFACT,
    QWEN_BARE_ARTIFACT,
    QWEN_MODEL,
    UNKNOWN_MODEL,
)


@pytest.mark.slow
def test_the_library_lists_each_kind_one_s_own_first(signed: TestClient) -> None:
    page = shown(signed, "/library?kind=reasoning")
    listed = signed.get("/api/threads", params={"kind": "reasoning"}).json()
    for t in listed:
        assert f'href="/threads/{t["id"]}"' in page
    mine = [t for t in listed if t["owner"] == "alice"]
    others = [t for t in listed if t["owner"] != "alice"]
    assert page.index(f'/threads/{mine[0]["id"]}"') < page.index(
        f'/threads/{others[0]["id"]}"'
    )
    assert 'href="/library?kind=case"' in page and "Library" in page
    assert "/library?kind=appendix" not in page
    assert signed.get("/library?kind=stack").status_code == 404


@pytest.mark.slow
def test_the_library_shelves_every_kind_under_its_heading_with_what_it_is(
    signed: TestClient,
) -> None:
    page = shown(signed, "/library")
    for shelf in SHELVES:
        assert f"{upfirst(shelf.heading)}</h2>" in page and shelf.about in page
        for word, about in shelf.kinds.items():
            assert f'href="/library?kind={word}"' in page and about in page
    listed = signed.get("/api/threads", params={"kind": "reasoning"}).json()
    mine = sum(t["owner"] == "alice" for t in listed)
    assert (
        "reasoning How much the model thinks before it answers, which can change the "
        + f"answer. {mine} yours · {len(listed) - mine} shared with you"
    ) in said(page)

    for word in ("tool", "expectation_schema", "canary_set", "reasoning"):
        [entry, *_] = re.findall(
            rf'href="/library\?kind={word}"[^>]*>(.*?)</a>', page, re.DOTALL
        )
        assert ("loaded with data sets" in entry) == (word != "reasoning"), word
    for word in ("case", "expectation"):
        [entry, *_] = re.findall(
            rf'href="/library\?kind={word}"[^>]*>(.*?)</a>', page, re.DOTALL
        )
        assert ("written in Review" in entry) == (word == "case"), word

    tab = shown(signed, "/library?kind=reasoning")
    assert 'href="/library?kind=reasoning" aria-current="page"' in tab
    assert escape("How much the model thinks before it answers") in tab
    assert re.findall(r'href="/library"( aria-current="page")?[^>]*>Overview', tab) == [
        "",
        "",
    ]


@pytest.mark.slow
def test_what_ops_ship_is_shelved_last_and_what_the_world_shows_isn_t(
    signed: TestClient,
) -> None:
    page = shown(signed, "/library")
    headings = re.findall(r"<h2[^>]*>([^<]+)</h2>", page)
    assert headings[-1] == "Operations" and "Models" not in headings
    for word in ("model", "engine", "facts"):
        assert f'href="/library?kind={word}"' not in page
        assert signed.get(f"/library?kind={word}").status_code == 404
    for word, card in (("model", "handle"), ("engine", "engine"), ("facts", "facts")):
        [held, *_] = signed.get("/api/threads", params={"kind": word}).json()
        page = shown(signed, f"/threads/{held['id']}")
        assert f'<a href="/world#{card}-{held["id"]}">← World</a>' in page
        assert '<a href="/world" aria-current="page"' in page
        assert '<a href="/library" aria-current="page"' not in page
    tool = thread(signed, "tool", "lookup", "archive")
    assert '<a href="/library" aria-current="page"' in shown(
        signed, f"/threads/{tool['id']}"
    )


@pytest.mark.slow
def test_a_shelf_is_found_in_by_what_is_said_and_its_cases_narrowed_by_tags(
    signed: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    listed = [
        t
        for purpose in ("generation", "judge")
        for t in signed.get(
            "/api/threads", params={"kind": "configuration", "purpose": purpose}
        ).json()
    ]
    # Accommodating for the test World's shelves, which are shorter than a page: a page
    # as long as the shelf gives it its search box.
    monkeypatch.setattr(settings, "ROWS_PER_PAGE", len(listed))
    native = thread(signed, "configuration", NATIVE)
    detail = signed.get(f"/api/threads/{native['id']}").json()
    page = shown(signed, "/library?kind=configuration")
    assert escape(detail["description"]) in page
    assert f"Find {len(listed)} of {len(listed)}" in said(page)
    words = detail["description"].split()[:2]
    found = shown(signed, f"/library?kind=configuration&q={' '.join(words).upper()}")
    assert f'href="/threads/{native["id"]}"' in found
    hidden = [t for t in listed if t["id"] != native["id"]]
    assert any(f'href="/threads/{t["id"]}"' not in found for t in hidden)
    nothing = shown(signed, "/library?kind=configuration&q=no-such-thing")
    assert "None you see." in nothing and "show every one" in nothing

    families = signed.get("/api/families").json()
    both = {f["id"] for f in families if {"bytes", "swedish"} <= set(f["tags"])}
    page = shown(signed, "/library?kind=case&tag=bytes&tag=swedish")
    assert (
        both
        and {f["id"] for f in families if f'href="/cases/{f["id"]}"' in page} == both
    )
    assert 'href="/library?kind=case&amp;tag=swedish"' in page
    assert (
        'href="/library?kind=case&amp;tag=bytes&amp;tag=swedish&amp;pick=all"' in page
    )
    assert " checked>" not in page
    every = shown(signed, "/library?kind=case&tag=bytes&tag=swedish&pick=all")
    assert every.count(" checked>") == len(both) and "Pick none" in every

    [targets] = signed.get("/api/threads", params={"kind": "expectation_schema"}).json()
    expected = signed.get("/api/threads", params={"kind": "expectation"}).json()
    under = shown(
        signed, f"/library?kind=expectation&schema={targets['head']['digest']}"
    )
    assert all(f'href="/threads/{t["id"]}"' in under for t in expected)
    none = shown(signed, "/library?kind=expectation&schema=sha256:0")
    assert "None you see." in none and 'href="/threads/' not in none


@pytest.mark.slow
def test_a_shelf_is_found_in_only_from_as_many_as_a_page_holds(
    signed: TestClient,
) -> None:
    for word in ("reasoning", "configuration"):
        held = len(signed.get("/api/threads", params={"kind": word}).json())
        page = shown(signed, f"/library?kind={word}")
        assert ('name="q"' in page) == (held >= settings.ROWS_PER_PAGE), word
        assert "<tbody data-paged>" in page and "<div data-finding" not in page


@pytest.mark.slow
def test_the_library_lists_configurations_of_either_purpose(signed: TestClient) -> None:
    page = shown(signed, "/library?kind=configuration")
    lines = thread(signed, "configuration", LINES)
    query = {"kind": "configuration", "purpose": "judge", "name": JUDGE}
    [judge] = signed.get("/api/threads", params={**query, "owner": "archive"}).json()
    for t in (lines, judge):
        assert f'href="/threads/{t["id"]}"' in page
    assert ">generation</td>" in page and ">judge</td>" in page


@pytest.mark.slow
def test_a_thread_s_page_holds_its_versions_and_what_is_said(
    signed: TestClient,
) -> None:
    off = thread(signed, "reasoning", OFF)
    page = shown(signed, f"/threads/{off['id']}")
    assert "<h2>Edit</h2>" in page and "Fork it" in page
    assert "Version 1 of 1" in page and "It is the first." in page
    assert f'action="/threads/{off["id"]}/edit"' in page
    assert 'href="/library" aria-current="page"' in page

    archives = thread(signed, "reasoning", OFF, "archive")
    page = shown(signed, f"/threads/{archives['id']}")
    assert "<h2>Edit</h2>" not in page and "Fork it" in page

    lines = thread(signed, "configuration", LINES)
    page = shown(signed, f"/threads/{lines['id']}")
    assert "<h2>Edit</h2>" in page
    assert f'href="/compose/{lines["id"]}"' in page


@pytest.mark.slow
def test_a_thread_s_fields_are_edited_by_its_owner_and_read_by_others(
    signed: TestClient,
) -> None:
    off = thread(signed, "reasoning", OFF)
    path = f"/threads/{off['id']}"
    given = submitted(shown(signed, path), f"{path}/edit")
    assert given == {
        "head": [str(off["head"]["id"])],
        "f.effort": [""],
        "f.thinking_token_budget": [""],
        "f.chat_template_kwargs": [""],
        "f.level": ["off"],
    }
    for typed, message in (
        ("a few", "thinking_token_budget isn&#39;t a whole number"),
        ("-1", "greater than or equal to 0"),
    ):
        changed = {**given, "f.thinking_token_budget": [typed]}
        got = signed.post(f"{path}/edit", data=changed)
        assert got.status_code == 422 and message in got.text
    changed = {**given, "f.thinking_token_budget": ["64"]}
    got = signed.post(f"{path}/edit", data=changed)
    assert (got.status_code, got.headers["location"]) == (303, path)
    head = signed.get(f"/api{path}").json()["head"]["digest"]
    body = signed.get(f"/api/components/{head}").json()["body"]
    assert body["thinking_token_budget"] == 64
    assert "Version 2 of 2" in shown(signed, path)
    got = signed.post(f"{path}/edit", data=changed)
    assert got.status_code == 409

    archives = thread(signed, "reasoning", OFF, "archive")
    page = shown(signed, f"/threads/{archives['id']}")
    assert "/edit" not in page and "Fork it as it is" in page
    lookup = thread(signed, "tool", "lookup", "archive")
    page = shown(signed, f"/threads/{lookup['id']}")
    assert "/edit" not in page and "Fork it" not in page

    lines = thread(signed, "output", LINES)
    path = f"/threads/{lines['id']}"
    assert submitted(shown(signed, path), f"{path}/edit")["language"] == ["en"]


@pytest.mark.slow
def test_a_scorer_s_views_are_offered_what_they_can_read_and_judges_to_ask(
    signed: TestClient,
) -> None:
    query = {"kind": "scorer", "name": "judged"}
    [judged] = signed.get("/api/threads", params=query).json()
    forks = f"/api/threads/{judged['id']}/forks"
    mine = signed.post(forks, json={"name": "mine"}).json()
    page = shown(signed, f"/threads/{mine['id']}")
    held = page.split('<script type="application/json" id="library-props">', 1)[1]
    scoring = json.loads(held.split("</script>", 1)[0])["scoring"]
    body = signed.get(f"/api/components/{judged['head']['digest']}").json()["body"]
    assert {v["judge"] for v in body["views"] if v["judge"]} <= set(scoring["titles"])
    judges = signed.get("/api/threads", params={"kind": "judge"}).json()
    assert {j["digest"] for j in scoring["judges"]} == {
        j["head"]["digest"] for j in judges
    }
    verdict = next(j for j in scoring["judges"] if j["name"] == "verdict")
    assert verdict["output_schema"]["title"] == "Verdict" and verdict["seeds"] == [1]
    assert not any("texts" in j for j in scoring["judges"])
    query = {"kind": "configuration", "purpose": "judge"}
    judging = signed.get("/api/threads", params=query).json()
    assert {j["digest"] for j in scoring["judging"]} == {
        j["head"]["digest"] for j in judging
    }
    assert {m["name"] for m in scoring["models"]} == {
        QWEN_ARTIFACT,
        QWEN_BARE_ARTIFACT,
        GPT_OSS_ARTIFACT,
        MISTRAL_ARTIFACT,
        UNKNOWN_MODEL,
    }
    code = signed.get("/api/scorer-code").json()[0]
    assert scoring["metrics"] == code["metrics"]
    assert None in {o["title"] for o in scoring["outputs"]}


@pytest.mark.slow
def test_a_thread_s_form_sent_as_it_is_writes_nothing(signed: TestClient) -> None:
    for word in (*CHUNK_PARTS, "expectation", "scorer", "judge"):
        query = {"kind": word, "owner": "alice"}
        for t in signed.get("/api/threads", params=query).json():
            path = f"/threads/{t['id']}"
            got = signed.post(
                f"{path}/edit", data=submitted(shown(signed, path), f"{path}/edit")
            )
            assert got.status_code == 303, (word, t["name"], got.text[:300])
            edits = signed.get(f"/api{path}/edits").json()
            assert len(edits) == 1, (word, t["name"])
    lines = thread(signed, "configuration", LINES)
    path = f"/threads/{lines['id']}"
    _ = signed.post(f"{path}/edit", data=submitted(shown(signed, path), f"{path}/edit"))
    assert len(signed.get(f"/api{path}/edits").json()) == 1


@pytest.mark.slow
def test_a_refused_form_is_shown_again_with_what_was_typed_and_why(
    signed: TestClient,
) -> None:
    off = thread(signed, "reasoning", OFF)
    path = f"/threads/{off['id']}"
    given = submitted(shown(signed, path), f"{path}/edit")
    broken = '"enable_thinking": fals'
    typed = {
        **given,
        "f.chat_template_kwargs": [broken],
        "f.thinking_token_budget": ["64"],
    }
    got = signed.post(f"{path}/edit", data=typed)
    assert got.status_code == 422 and "Nothing is saved yet" in got.text
    assert '<dt class="text-destructive">chat template kwargs</dt>' in got.text
    assert "chat_template_kwargs isn&#39;t JSON" in got.text
    again = submitted(got.text, f"{path}/edit")
    assert (again["f.chat_template_kwargs"], again["f.thinking_token_budget"]) == (
        [broken],
        ["64"],
    )
    assert len(signed.get(f"/api{path}/edits").json()) == 1

    action = "/library/new?kind=sampling"
    written = {
        **submitted(shown(signed, action), action),
        "name": ["capped"],
        "f.max_output_tokens": ["0"],
        "f.stop": ["</s>"],
    }
    got = signed.post(action, data=written)
    assert got.status_code == 422
    assert '<dt class="text-destructive">max output tokens</dt>' in got.text
    assert "greater than or equal to 1" in got.text
    again = submitted(got.text, action)
    assert (again["name"], again["f.max_output_tokens"], again["f.stop"]) == (
        ["capped"],
        ["0"],
        ["</s>"],
    )
    got = signed.post(action, data={**written, "name": [" "]})
    assert 'name="name" required pattern=".*\\S.*"' in got.text
    assert '<dt class="text-destructive">max output tokens</dt>' in got.text

    said = {"name": "quiet", "description": "Thinks not.", "tags": "a"}
    got = signed.post(f"{path}/said", data={**said, "shared": "nobody-at-all"})
    assert got.status_code == 422 and "no person" in got.text
    assert submitted(got.text, f"{path}/said") == {
        **{k: [v] for k, v in said.items()},
        "shared": ["nobody-at-all"],
    }
    assert signed.get(f"/api{path}").json()["name"] != "quiet"

    lines = thread(signed, "configuration", LINES)
    asked = {"kind": "translations", "configuration": lines["id"], "into": "swedish"}
    got = signed.get("/library/new", params=asked)
    assert got.status_code == 422 and "is not a language tag" in got.text
    assert 'name="into"' in got.text and "Nothing is saved yet" not in got.text


@pytest.mark.slow
def test_a_toolset_s_tools_are_picked_one_a_line(signed: TestClient) -> None:
    toolset = signed.get(
        "/api/threads", params={"kind": "toolset", "owner": "alice"}
    ).json()[0]
    path = f"/threads/{toolset['id']}"
    page = shown(signed, path)
    given = submitted(page, f"{path}/edit")
    body = signed.get(f"/api/components/{toolset['head']['digest']}").json()["body"]
    assert given["f.tools"] == [*body["tools"], ""]
    tools = signed.get("/api/threads", params={"kind": "tool"}).json()
    for t in tools:
        assert f'<option value="{t["head"]["digest"]}"' in page
    kept = body["tools"][1:]
    got = signed.post(f"{path}/edit", data={**given, "f.tools": [*kept, "", ""]})
    assert got.status_code == 303
    head = signed.get(f"/api{path}").json()["head"]["digest"]
    held = signed.get(f"/api/components/{head}").json()["body"]
    assert held["tools"] == kept


@pytest.mark.slow
def test_a_configuration_s_recipe_parts_are_picked(signed: TestClient) -> None:
    lines = thread(signed, "configuration", LINES)
    path = f"/threads/{lines['id']}"
    page = shown(signed, path)
    given = submitted(page, f"{path}/edit")
    assert set(given) == {"head", *(f"f.{p}" for p in RECIPE_PARTS)}
    assert (
        page.index("<h3>Recipe</h3>")
        < page.index(">Request</summary>")
        < page.index(">messages<")
    )
    recipe = signed.get(f"/api{path}").json()["recipe"]
    assert given["f.model"] == [recipe["model"]]
    prompt = signed.get("/api/threads", params={"kind": "prompt", "owner": "alice"})
    held = {t["head"]["digest"]: t["id"] for t in prompt.json()}
    assert f'href="/threads/{held[recipe["prompt"]]}">Open the one picked' in page
    off = thread(signed, "reasoning", OFF)
    got = signed.post(
        f"{path}/edit", data={**given, "f.reasoning": [off["head"]["digest"]]}
    )
    assert got.status_code == 303
    recipe = signed.get(f"/api{path}").json()["recipe"]
    assert recipe["reasoning"] == off["head"]["digest"]
    page = shown(signed, path)
    assert "Version 2 of 2" in page
    assert "<h3>Changes</h3>" in page
    assert f"/reasoning — → {OFF}" in said(page)


@pytest.mark.slow
def test_what_a_thread_refers_to_is_linked_where_it_is_seen(signed: TestClient) -> None:
    lines = thread(signed, "scorer", "lines", "archive")
    [targets] = signed.get("/api/threads", params={"kind": "expectation_schema"}).json()
    page = shown(signed, f"/threads/{lines['id']}")
    assert f'href="/threads/{targets["id"]}">{targets["name"]}</a>' in page

    [mine] = signed.get(
        "/api/threads", params={"kind": "expectation", "owner": "alice"}
    ).json()[:1]
    case = signed.get(f"/api/components/{mine['head']['digest']}").json()["body"][
        "case"
    ]
    [family] = [
        f
        for f in signed.get("/api/families").json()
        if case
        in [c["case"] for c in signed.get(f"/api/families/{f['id']}").json()["cases"]]
    ]
    page = shown(signed, f"/threads/{mine['id']}")
    assert f'href="/cases/{family["id"]}">' in page


@pytest.mark.slow
def test_every_kind_a_person_writes_is_begun_from_the_library(
    signed: TestClient,
) -> None:
    for word in ("configuration", *CHUNK_PARTS, "scorer", "judge", "expectation"):
        assert f'href="/library/new?kind={word}"' in shown(
            signed, f"/library?kind={word}"
        )
        begun = signed.get(f"/library/new?kind={word}", follow_redirects=True).text
        assert ("Show its texts" if word == "translations" else "Write it") in begun
        if word in ("instructions", "translations"):
            assert 'pattern="[a-z]{2,3}(-[A-Za-z0-9]{1,8})*"' in begun
    for word in ("tool", "expectation_schema", "canary_set"):
        assert "/library/new" not in shown(signed, f"/library?kind={word}")
        assert signed.get(f"/library/new?kind={word}").status_code == 404
    for word in ("model", "engine", "facts"):
        assert signed.get(f"/library/new?kind={word}").status_code == 404
    assert signed.get("/library/new?kind=stack").status_code == 404


@pytest.mark.slow
def test_a_chunk_is_written_from_nothing(signed: TestClient) -> None:
    action = "/library/new?kind=sampling"
    given = submitted(shown(signed, action), action)
    assert (given["name"], given["f.temperature"], given["f.max_tokens_key"]) == (
        [""],
        [""],
        ["max_completion_tokens"],
    )
    got = signed.post(action, data={**given, "f.temperature": ["0.3"]})
    assert got.status_code == 422
    assert 'name="name" required pattern=".*\\S.*"' in got.text
    assert submitted(got.text, action)["f.temperature"] == ["0.3"]
    got = signed.post(
        action, data={**given, "name": ["warm"], "f.temperature": ["0.3"]}
    )
    assert got.status_code == 303
    warm = signed.get(f"/api{got.headers['location']}").json()
    assert (warm["name"], warm["owner"]) == ("warm", "alice")
    body = signed.get(f"/api/components/{warm['head']['digest']}").json()["body"]
    assert body["temperature"] == 0.3

    action = "/library/new?kind=instructions"
    given = submitted(shown(signed, action), action)
    assert (given["as.text"], given["language"]) == (["text"], [""])
    written = {**given, "name": ["brief"], "f.text": ["Be brief."]}
    got = signed.post(action, data={**written, "language": ["en"]})
    brief = signed.get(f"/api{got.headers['location']}").json()
    assert brief["language"] == "en"


@pytest.mark.slow
def test_a_judge_s_configuration_model_and_seeds_are_edited_on_its_page(
    signed: TestClient, conn: Connection, alice: Person
) -> None:
    verdict = thread(signed, "judge", "verdict", "archive")
    page = f"/threads/{verdict['id']}"
    assert "/edit" not in shown(signed, page)
    body = signed.get(f"/api/components/{verdict['head']['digest']}").json()["body"]
    handles = signed.get("/api/threads", params={"kind": "model"}).json()
    models = {t["name"]: t["head"]["digest"] for t in handles}
    assert body["model"] == models[QWEN_ARTIFACT]

    made = signed.post(
        "/api/threads", json={"component": {**body, "seeds": [4]}, "name": "mine"}
    ).json()
    path = f"/threads/{made['id']}"
    shown_page = shown(signed, path)
    given = submitted(shown_page, f"{path}/edit")
    assert (given["f.skeleton"], given["f.model"]) == (
        [body["skeleton"]],
        [models[QWEN_ARTIFACT]],
    )
    assert f'value="{models[GPT_OSS_ARTIFACT]}"' in shown_page
    changed = {**given, "f.model": [models[GPT_OSS_ARTIFACT]], "f.seeds": ["3"]}
    assert signed.post(f"{path}/edit", data=changed).status_code == 303
    head = signed.get(f"/api{path}").json()["head"]["digest"]
    held = signed.get(f"/api/components/{head}").json()["body"]
    assert (held["seeds"], held["model"]) == ([3], models[GPT_OSS_ARTIFACT])
    found = signed.post("/api/components/check", json=held).json()["findings"]
    page_now = shown(signed, path)
    assert found and all(f["code"] in page_now for f in found)

    store = Store(conn)
    registry = store.load([])
    weights = registry.add(
        LocalModel(
            repo=QWEN_MODEL,
            revision="newer",
            files=(FileDigest(path="none", sha256="0" * 64),),
        )
    )
    _ = store.add(registry, [weights])
    handle = thread(signed, "model", QWEN_ARTIFACT, "archive")
    _ = Catalog(conn).edit(handle["id"], weights, alice.id)
    assert "verdict is out of date: update it on its page" in shown(signed, page)


@pytest.mark.slow
def test_a_form_is_checked_as_typed_and_nothing_is_written(signed: TestClient) -> None:
    action = "/library/new?kind=sampling"
    page = shown(signed, action)
    assert "data-checked" in page and 'id="library-props"' in page
    given = submitted(page, action)
    before = signed.get("/api/threads", params={"kind": "sampling"}).json()
    refused = {**given, "name": ["warm"], "f.temperature": ["warm"], "checking": ["1"]}
    got = signed.post(action, data=refused)
    assert got.status_code == 200 and got.json()["refused"][0].startswith(
        "temperature: "
    )
    fine = {**given, "name": ["warm"], "f.temperature": ["0.3"], "checking": ["1"]}
    assert signed.post(action, data=fine).json() == {"refused": []}
    after = signed.get("/api/threads", params={"kind": "sampling"}).json()
    assert after == before


@pytest.mark.slow
def test_a_recipe_is_checked_as_typed_by_compiling_it(signed: TestClient) -> None:
    action = "/library/new?kind=configuration"
    given = submitted(shown(signed, action), action)
    models = signed.get("/api/threads", params={"kind": "model"}).json()
    mistral = next(m for m in models if "mistral" in (m["name"] or m["title"]))
    high = thread(signed, "reasoning", "high", "archive")["head"]["digest"]
    case, lines, greedy = (
        thread(signed, kind, name, "archive")["head"]["digest"]
        for kind, name in (
            ("prompt", "case"),
            ("output", "lines"),
            ("sampling", "greedy"),
        )
    )
    picks = {
        **given,
        "f.prompt": [case],
        "f.output": [lines],
        "f.sampling": [greedy],
        "f.model": [mistral["head"]["digest"]],
    }
    before = signed.get("/api/threads", params={"kind": "configuration"}).json()
    asked = {**picks, "f.reasoning": [high], "checking": ["1"]}
    assert signed.post(action, data=asked).json()["refused"]
    assert signed.post(action, data={**picks, "checking": ["1"]}).json() == {
        "refused": []
    }
    assert signed.get("/api/threads", params={"kind": "configuration"}).json() == before


@pytest.mark.slow
def test_numbers_checks_and_lists_are_written_as_such(signed: TestClient) -> None:
    action = "/library/new?kind=sampling"
    page = shown(signed, action)
    for control in (
        '<input type="number" name="f.temperature" aria-label="temperature" value="" '
        + 'step="any"',
        'name="f.max_output_tokens" aria-label="max output tokens" value="" step="1" '
        + 'min="1"',
        '<input type="checkbox" name="f.recommended" value="true"',
    ):
        assert control in page
    given = submitted(page, action)
    assert "f.recommended" not in given and given["f.stop"] == [""]
    written = {
        **given,
        "name": ["stopping"],
        "f.temperature": ["0.5"],
        "f.max_output_tokens": ["256"],
        "f.stop": ["</s>\r\n\r\nEND\r\n"],
        "f.recommended": ["true"],
    }
    got = signed.post(action, data=written)
    assert got.status_code == 303
    path = got.headers["location"]
    made = signed.get(f"/api{path}").json()
    body = signed.get(f"/api/components/{made['head']['digest']}").json()["body"]
    assert (body["temperature"], body["max_output_tokens"]) == (0.5, 256)
    assert (body["stop"], body["recommended"]) == (["</s>", "END"], True)

    given = submitted(shown(signed, path), f"{path}/edit")
    assert (given["f.temperature"], given["f.stop"], given["f.recommended"]) == (
        ["0.5"],
        ["</s>\nEND"],
        ["true"],
    )
    got = signed.post(f"{path}/edit", data={**given, "f.max_output_tokens": ["1.5"]})
    assert (
        got.status_code == 422
        and "max_output_tokens isn&#39;t a whole number" in got.text
    )
    unchecked = {k: v for k, v in given.items() if k != "f.recommended"}
    got = signed.post(f"{path}/edit", data={**unchecked, "f.temperature": [""]})
    assert got.status_code == 303
    head = signed.get(f"/api{path}").json()["head"]["digest"]
    body = signed.get(f"/api/components/{head}").json()["body"]
    assert (body["recommended"], body["temperature"]) == (False, None)


@pytest.mark.slow
def test_a_judge_is_written_from_nothing(signed: TestClient) -> None:
    action = "/library/new?kind=judge"
    given = submitted(shown(signed, action), action)
    assert (given["f.skeleton"], given["f.model"], given["f.fill"]) == (
        [""],
        [""],
        ["text@1"],
    )
    verdict = thread(signed, "judge", "verdict", "archive")
    body = signed.get(f"/api/components/{verdict['head']['digest']}").json()["body"]
    got = signed.post(action, data={**given, "name": ["strict"], "f.seeds": ["2"]})
    assert got.status_code == 422 and "skeleton" in got.text
    picked = {"f.skeleton": [body["skeleton"]], "f.model": [body["model"]]}
    got = signed.post(
        action, data={**given, **picked, "name": ["strict"], "f.seeds": ["2"]}
    )
    assert got.status_code == 303
    strict = signed.get(f"/api{got.headers['location']}").json()
    held = signed.get(f"/api/components/{strict['head']['digest']}").json()["body"]
    assert held == {**body, "seeds": [2]}


@pytest.mark.slow
def test_a_scorer_s_views_and_labels_are_edited_on_its_page(signed: TestClient) -> None:
    lines = thread(signed, "scorer", "lines", "archive")
    assert "/edit" not in shown(signed, f"/threads/{lines['id']}")
    [targets] = signed.get(
        "/api/threads", params={"kind": "expectation_schema", "name": "targets"}
    ).json()
    forked = signed.post(
        f"/api/threads/{lines['id']}/forks", json={"name": "my lines"}
    ).json()
    path = f"/threads/{forked['id']}"
    given = submitted(shown(signed, path), f"{path}/edit")
    assert given["f.expectation_schema"] == [targets["head"]["digest"]]
    labels = {"views": ["text", "differential", "dont-miss"], "resources": []}
    assert json.loads(given["labels"][0]) == labels

    views = json.loads(f"[{given['f.views'][0]}]")
    moved = [views[1], views[0], *views[2:]]
    renamed = {"views": ["differential", "first", "dont-miss"]}
    changed = {
        **given,
        "f.views": [json.dumps(moved)[1:-1]],
        "labels": [json.dumps(renamed)],
    }
    assert signed.post(f"{path}/edit", data=changed).status_code == 303
    head = signed.get(f"/api{path}").json()["head"]
    held = signed.get(f"/api/components/{head['digest']}").json()["body"]
    assert held["views"] == moved
    assert head["labels"]["views"] == renamed["views"]


@pytest.mark.slow
def test_a_scorer_of_code_that_isn_t_shipped_says_to_write_a_new_one(
    signed: TestClient, conn: Connection, alice: Person
) -> None:
    lines = thread(signed, "scorer", "lines", "archive")
    store = Store(conn)
    registry = store.load([lines["head"]["digest"]])
    held = resolve(registry.get, lines["head"]["digest"], Scorer)
    old = registry.add(held.model_copy(update={"version": held.version + 1}))
    _ = store.add(registry, [old])
    made = Catalog(conn).create(old, alice.id, name="old lines")
    page = shown(signed, f"/threads/{made.thread}")
    assert f'action="/threads/{made.thread}/edit"' not in page
    said = f"{held.entry_point} is at version {held.version} in chatddx "
    assert said in page
    assert f", not {held.version + 1}: create a new scorer to score with" in page


@pytest.mark.slow
def test_a_scorer_is_written_from_nothing_with_its_labels(signed: TestClient) -> None:
    lines = thread(signed, "scorer", "lines", "archive")
    body = signed.get(f"/api/components/{lines['head']['digest']}").json()["body"]
    got = signed.get("/library/new?kind=scorer", follow_redirects=False)
    assert got.status_code == 303
    action = got.headers["location"]
    page = shown(signed, action)
    assert 'name="f.entry_point"' not in page and body["entry_point"] in page
    given = submitted(page, action)
    assert json.loads(given["labels"][0]) == {"views": [], "resources": []}
    written = {
        **given,
        "name": ["mine"],
        "f.expectation_schema": [body["expectation_schema"]],
        "f.views": [json.dumps(body["views"])[1:-1]],
        "labels": [json.dumps({"views": ["a", "b", "c"]})],
    }
    got = signed.post(action, data=written)
    assert got.status_code == 303
    mine = signed.get(f"/api{got.headers['location']}").json()
    assert mine["head"]["digest"] == lines["head"]["digest"]
    assert mine["head"]["labels"]["views"] == ["a", "b", "c"]


@pytest.mark.slow
def test_an_expectation_is_written_from_nothing_and_an_appendix_only_in_review(
    signed: TestClient,
) -> None:
    assert signed.get("/library?kind=appendix").status_code == 404
    for kind in ("appendix", "case"):
        got = signed.get("/library/new", params={"kind": kind})
        assert got.status_code == 404 and f"no {kind} is begun here" in got.text
    crlf = family(signed)
    given = {"name": "fluid", "text": "Free fluid."}
    got = signed.post(f"/api/families/{crlf['id']}/appendices", json=given)
    assert got.status_code == 201
    fluid = got.json()
    got = signed.get(f"/threads/{fluid['id']}")
    assert got.status_code == 404 and "it is in Review" in got.text

    [mine] = signed.get(
        "/api/threads", params={"kind": "expectation", "owner": "alice"}
    ).json()[:1]
    expected = signed.get(f"/api/components/{mine['head']['digest']}").json()["body"]
    action = "/library/new?kind=expectation"
    page = shown(signed, action)
    assert f'<option value="{expected["case"]}"' in page
    written = {
        **submitted(page, action),
        "name": ["again"],
        "f.case": [expected["case"]],
        "f.expectation_schema": [expected["expectation_schema"]],
        "f.data": [json.dumps(expected["data"])],
    }
    got = signed.post(action, data=written)
    assert got.status_code == 422 and "already, in thread" in got.text


@pytest.mark.slow
def test_an_expectation_stays_of_its_case_and_a_case_is_picked_by_its_title(
    signed: TestClient,
) -> None:
    [mine] = signed.get(
        "/api/threads", params={"kind": "expectation", "owner": "alice"}
    ).json()[:1]
    path = f"/threads/{mine['id']}"
    page = shown(signed, path)
    assert 'name="f.case"' not in page and 'name="f.expectation_schema"' not in page
    assert 'name="f.data"' in page and 'id="library-props"' in page
    given = submitted(page, f"{path}/edit")
    assert signed.post(f"{path}/edit", data=given).status_code == 303
    assert len(signed.get(f"/api{path}/edits").json()) == 1

    crlf = family(signed)
    begun = shown(signed, "/library/new?kind=expectation")
    for c in signed.get(f"/api/families/{crlf['id']}").json()["cases"]:
        assert re.search(
            rf'<option value="{c["case"]}">crlf( with [^<]+)?</option>', begun
        )
    archives = thread(signed, "reasoning", OFF, "archive")
    assert 'id="library-props"' not in shown(signed, f"/threads/{archives['id']}")


@pytest.mark.slow
def test_a_configuration_is_written_from_a_recipe(signed: TestClient) -> None:
    action = "/library/new?kind=configuration"
    given = submitted(shown(signed, action), action)
    assert (given["f.purpose"], given["f.prompt"], given["f.reasoning"]) == (
        ["generation"],
        [""],
        [""],
    )
    lines = thread(signed, "configuration", LINES)
    recipe = signed.get(f"/api/threads/{lines['id']}").json()["recipe"]
    parts = {f"f.{p}": [recipe[p] or ""] for p in RECIPE_PARTS}
    got = signed.post(action, data={**given, **parts, "name": ["lines again"]})
    assert got.status_code == 303
    again = signed.get(f"/api{got.headers['location']}").json()
    assert again["recipe"] == recipe
    page = shown(signed, "/library?kind=configuration")
    assert 'href="/library/new?kind=configuration"' in page


@pytest.mark.slow
def test_what_is_said_of_a_thread_is_changed_and_it_is_deleted_and_restored(
    signed: TestClient,
) -> None:
    off = thread(signed, "reasoning", OFF)
    path = f"/threads/{off['id']}"
    form = {
        "name": "quiet",
        "description": "No thinking.",
        "tags": "b, a",
        "shared": "",
    }
    got = signed.post(f"{path}/said", data=form)
    assert (got.status_code, got.headers["location"]) == (303, path)
    said = signed.get(f"/api/threads/{off['id']}").json()
    assert (said["name"], said["description"], said["tags"]) == (
        "quiet",
        "No thinking.",
        ["a", "b"],
    )

    got = signed.post(f"{path}/said", data={**form, "shared": "nobody-at-all"})
    assert got.status_code == 422 and "no person" in got.text
    assert (
        signed.post(f"{path}/said", data={**form, "description": ""}).status_code == 303
    )
    assert signed.get(f"/api/threads/{off['id']}").json()["description"] is None

    assert signed.post(f"{path}/delete").status_code == 303
    page = shown(signed, path)
    assert "You deleted it" in page and "<h2>Edit</h2>" not in page
    assert f'action="{path}/restore"' in shown(signed, "/library?kind=reasoning")
    assert f'action="{path}/restore"' not in shown(signed, "/library?kind=sampling")
    assert signed.post(f"{path}/restore").status_code == 303
    assert "You deleted it" not in shown(signed, path)


@pytest.mark.slow
def test_a_configuration_is_said_of_deleted_and_restored_whatever_its_purpose(
    signed: TestClient,
) -> None:
    query = {"kind": "configuration", "purpose": "judge", "name": JUDGE}
    [judge] = signed.get("/api/threads", params={**query, "owner": "archive"}).json()
    got = signed.post(f"/threads/{judge['id']}/fork", data={"name": "strict"})
    assert got.status_code == 303
    path = got.headers["location"]
    form = {"name": "stricter", "description": "", "tags": "mine", "shared": "archive"}
    assert signed.post(f"{path}/said", data=form).status_code == 303
    said = signed.get(f"/api{path}").json()
    assert (said["name"], said["tags"], said["collaborators"]) == (
        "stricter",
        ["mine"],
        ["archive"],
    )
    form = {**form, "shared": ""}
    assert signed.post(f"{path}/said", data=form).status_code == 303
    assert signed.get(f"/api{path}").json()["collaborators"] == []

    assert signed.post(f"{path}/delete").status_code == 303
    assert f'action="{path}/restore"' in shown(signed, "/library?kind=configuration")
    assert "You deleted it" in shown(signed, path)
    assert signed.post(f"{path}/restore").status_code == 303


@pytest.mark.slow
def test_a_collaborator_leaves_a_thread_shared_with_them(signed: TestClient) -> None:
    archives = thread(signed, "reasoning", OFF, "archive")
    path = f"/threads/{archives['id']}"
    page = shown(signed, path)
    assert "Shared with you" in page and f'action="{path}/leave"' in page
    got = signed.post(f"{path}/leave")
    assert (got.status_code, got.headers["location"]) == (
        303,
        "/library?kind=reasoning",
    )
    assert f'href="{path}"' not in shown(signed, "/library?kind=reasoning")
    assert signed.get(path).status_code == 404

    mine = thread(signed, "reasoning", OFF)
    assert "Shared with you" not in shown(signed, f"/threads/{mine['id']}")
    got = signed.post(f"/threads/{mine['id']}/leave")
    assert got.status_code == 422 and "shared with alice" in got.text


@pytest.mark.slow
def test_a_fork_is_updated_from_its_origin_once_that_moves_on(
    signed: TestClient,
) -> None:
    off = thread(signed, "reasoning", OFF)
    got = signed.post(f"/threads/{off['id']}/fork", data={"name": "mine too"})
    assert got.status_code == 303
    fork = int(got.headers["location"].removeprefix("/threads/"))
    page = shown(signed, f"/threads/{fork}")
    assert f'href="/threads/{off["id"]}">{OFF}</a>' in page
    listed = said(shown(signed, "/library?kind=reasoning"))
    assert f"mine too forked from {OFF} alice" in listed
    assert f"{OFF} forked from archive/{OFF} alice" in listed
    assert "Its origin has a newer version." not in page

    body = signed.get(f"/api/components/{off['head']['digest']}").json()["body"]
    edits = f"/api/threads/{off['id']}/edits"
    moved = {**body, "thinking_token_budget": 64}
    got = signed.post(edits, json={"head": off["head"]["id"], "component": moved})
    assert got.status_code == 201
    page = shown(signed, f"/threads/{fork}")
    assert "Its origin has a newer version." in page
    head = signed.get(f"/api/threads/{fork}").json()["head"]
    assert (
        signed.post(f"/threads/{fork}/update", data={"head": head["id"]}).status_code
        == 303
    )
    assert "Its origin has a newer version." not in shown(signed, f"/threads/{fork}")
    assert "Version 2 of 2" in shown(signed, f"/threads/{fork}")


@pytest.mark.slow
def test_a_thread_s_versions_are_stepped_through_by_link(signed: TestClient) -> None:
    off = thread(signed, "reasoning", OFF)
    path = f"/threads/{off['id']}"
    body = signed.get(f"/api/components/{off['head']['digest']}").json()["body"]
    moved = {**body, "thinking_token_budget": 64}
    edits = f"/api{path}/edits"
    got = signed.post(edits, json={"head": off["head"]["id"], "component": moved})
    assert got.status_code == 201

    latest = shown(signed, path)
    assert "Version 2 of 2" in latest and f'href="{path}?version=1"' in latest
    assert "/thinking_token_budget" in latest and f'action="{path}/edit"' in latest
    first = shown(signed, f"{path}?version=1")
    assert "Version 1 of 2" in first and "It is the first." in first
    assert "Newer version: saved" in first and f'action="{path}/revert"' in first
    assert f'action="{path}/edit"' not in first
    for missing in (0, 3):
        got = signed.get(f"{path}?version={missing}")
        assert got.status_code == 404
        assert f"no version {missing} of reasoning {off['id']}: it has 2" in got.text

    archives = thread(signed, "reasoning", OFF, "archive")
    page = shown(signed, f"/threads/{archives['id']}?version=1")
    assert "Version 1 of 1" in page and "/revert" not in page


@pytest.mark.slow
def test_an_earlier_version_is_made_the_latest_as_an_edit(signed: TestClient) -> None:
    off = thread(signed, "reasoning", OFF)
    path = f"/threads/{off['id']}"
    body = signed.get(f"/api/components/{off['head']['digest']}").json()["body"]
    moved = {**body, "thinking_token_budget": 64}
    edits = f"/api{path}/edits"
    head = signed.post(edits, json={"head": off["head"]["id"], "component": moved})
    form = {"head": head.json()["id"], "edit": off["head"]["id"]}
    got = signed.post(f"{path}/revert", data=form)
    assert (got.status_code, got.headers["location"]) == (303, path)
    versions = signed.get(edits).json()
    assert [v["digest"] for v in versions] == [
        off["head"]["digest"],
        head.json()["digest"],
        off["head"]["digest"],
    ]
    assert [v["version"] for v in versions] == [1, 2, 1]
    page = shown(signed, path)
    assert "Version 1 of 2" in page and "Newer version: saved" not in page
    assert f'name="edit" value="{versions[-1]["id"]}"' not in page
    page = shown(signed, f"{path}?version=2")
    assert "Version 2 of 2" in page and "Newer version: saved" in page
    assert f'name="edit" value="{head.json()["id"]}"' in page

    later = signed.post(
        edits,
        json={
            "head": versions[-1]["id"],
            "component": {**body, "thinking_token_budget": 32},
        },
    )
    assert later.status_code == 201
    page = shown(signed, path)
    assert "Version 3 of 3" in page
    assert "Against version 1, the one it was saved over." in page
    form = {"head": later.json()["id"], "edit": off["head"]["id"]}
    got = signed.post(f"{path}/revert", data={**form, "head": head.json()["id"]})
    assert got.status_code == 409
    got = signed.post(f"{path}/revert", data={**form, "edit": 1})
    assert got.status_code == 422 and f"isn&#39;t a version of thread {off['id']}" in (
        got.text
    )

    archives = thread(signed, "reasoning", OFF, "archive")
    form = {"head": archives["head"]["id"], "edit": archives["head"]["id"]}
    got = signed.post(f"/threads/{archives['id']}/revert", data=form)
    assert got.status_code == 404


@pytest.mark.slow
def test_a_configuration_s_earlier_version_is_made_the_latest(
    signed: TestClient,
) -> None:
    lines = thread(signed, "configuration", LINES)
    path = f"/threads/{lines['id']}"
    off = thread(signed, "reasoning", OFF)["head"]["digest"]
    edits = f"/api{path}/edits"
    first = lines["head"]["id"]
    later = signed.post(edits, json={"head": first, "parts": {"reasoning": off}})
    assert later.status_code == 201
    form = {"head": later.json()["id"], "edit": first}
    assert signed.post(f"{path}/revert", data=form).status_code == 303
    versions = signed.get(edits).json()
    assert len(versions) == 3 and versions[-1]["digest"] == lines["head"]["digest"]


@pytest.mark.slow
def test_a_scorer_s_earlier_version_is_made_the_latest_with_its_labels(
    signed: TestClient,
) -> None:
    lines = thread(signed, "scorer", "lines", "archive")
    forks = f"/api/threads/{lines['id']}/forks"
    mine = signed.post(forks, json={"name": "my lines"}).json()
    body = signed.get(f"/api/components/{mine['head']['digest']}").json()["body"]
    edits = f"/api/threads/{mine['id']}/edits"
    renamed = {"views": ["first", "second", "third"]}
    asked = {"head": mine["head"]["id"], "component": body, "labels": renamed}
    later = signed.post(edits, json=asked)
    assert later.status_code == 201
    form = {"head": later.json()["id"], "edit": mine["head"]["id"]}
    assert signed.post(f"/threads/{mine['id']}/revert", data=form).status_code == 303
    first, renaming, reverted = signed.get(edits).json()
    assert renaming["labels"]["views"] == renamed["views"]
    assert reverted["labels"] == first["labels"] != renaming["labels"]


@pytest.mark.slow
def test_a_thread_s_forms_from_another_site_write_nothing(signed: TestClient) -> None:
    elsewhere = {"Sec-Fetch-Site": "cross-site"}
    actions = ("said", "edit", "delete", "restore", "leave", "revert", "fork")
    actions = (*actions, "update", "take")
    for action in (*actions, "carry"):
        assert signed.post(f"/threads/1/{action}", headers=elsewhere).status_code == 403
    assert signed.post("/library/update", headers=elsewhere).status_code == 403
