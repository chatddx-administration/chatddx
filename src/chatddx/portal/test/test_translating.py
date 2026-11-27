import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chatddx.portal.test.helpers import shown, submitted
from chatddx.test.helpers import INSTRUCTION
from chatddx.test.world import LINES, LINES_GUIDED


def mine(signed: TestClient, kind: str, name: str | None = None) -> dict[str, Any]:
    query = {"kind": kind, "owner": "alice", **({"name": name} if name else {})}
    [found] = signed.get("/api/threads", params=query).json()
    return found


def into(signed: TestClient, thread: dict[str, Any]) -> dict[str, dict[str, str]]:
    detail = signed.get(f"/api/threads/{thread['id']}").json()
    return signed.get(f"/api/components/{detail['head']['digest']}").json()["body"][
        "into"
    ]


def entries(form: dict[str, list[str]]) -> dict[str, str]:
    return {
        json.loads(form[key][0]): form[f"t.{key.removeprefix('s.')}"][0]
        for key in form
        if key.startswith("s.")
    }


@pytest.mark.slow
def test_a_translations_thread_s_page_shows_its_entries_by_language(
    signed: TestClient,
) -> None:
    guided = mine(signed, "translations")
    path = f"/threads/{guided['id']}"
    page = shown(signed, path)
    swedish = into(signed, guided)["sv"]
    given = submitted(page, f"{path}/edit")

    assert given["into"] == ["sv"] and entries(given) == swedish
    assert "⏎\n⏎\nAppendices:⏎" in page
    configuration = mine(signed, "configuration", LINES_GUIDED)
    assert f'href="/threads/{configuration["id"]}">{LINES_GUIDED}</a>' in page
    assert "Not translated yet" not in page


@pytest.mark.slow
def test_a_translation_is_changed_and_one_is_left_out(signed: TestClient) -> None:
    guided = mine(signed, "translations")
    path = f"/threads/{guided['id']}"
    given = submitted(shown(signed, path), f"{path}/edit")
    at = {json.loads(given[k][0]): k.removeprefix("s.") for k in given if k[:2] == "s."}
    output = "List the plausible diagnoses, one per line, most likely first."
    worked = "Acute coronary syndrome\nAortic dissection\nPulmonary embolism"
    changed = {
        **given,
        f"t.{at[INSTRUCTION]}": ["Du hjälper en läkare.\r\nLäs fallet."],
        f"out.{at[worked]}": ["1"],
    }

    got = signed.post(f"{path}/edit", data=changed)
    assert (got.status_code, got.headers["location"]) == (303, f"{path}?into=sv")
    swedish = into(signed, guided)["sv"]
    assert swedish[INSTRUCTION] == "Du hjälper en läkare.\nLäs fallet."
    assert worked not in swedish and output in swedish

    page = shown(signed, f"{path}?into=sv")
    assert "Not translated yet" in page and "Akut koronart syndrom" in page
    latest = signed.get(f"/api/threads/{guided['id']}").json()["head"]["digest"]
    assert f"?translations={latest.replace(':', '%3A')}" in page
    again = signed.post(f"{path}/edit", data=changed)
    assert again.status_code == 409


@pytest.mark.slow
def test_a_text_its_configuration_sends_untranslated_starts_from_a_similar_one(
    signed: TestClient,
) -> None:
    clinician = mine(signed, "instructions", "clinician")
    body = signed.get(f"/api/components/{clinician['head']['digest']}").json()["body"]
    longer = INSTRUCTION.removesuffix(".") + " and plan."
    edited = signed.post(
        f"/api/threads/{clinician['id']}/edits",
        json={"head": clinician["head"]["id"], "component": {**body, "text": longer}},
    )
    assert edited.status_code == 201, edited.json()
    configuration = mine(signed, "configuration", LINES_GUIDED)
    moved = signed.post(
        f"/api/threads/{configuration['id']}/edits",
        json={
            "head": configuration["head"]["id"],
            "parts": {"instructions": edited.json()["digest"]},
        },
    )
    assert moved.status_code == 201, moved.json()

    guided = mine(signed, "translations")
    path = f"/threads/{guided['id']}"
    page = shown(signed, path)
    offered = entries(submitted(page, f"{path}/edit"))
    swedish = into(signed, guided)["sv"]
    assert offered[longer] == swedish[INSTRUCTION] == offered[INSTRUCTION]
    assert "Not translated yet: started from" in page


@pytest.mark.slow
def test_a_language_is_added_with_the_texts_its_configurations_send(
    signed: TestClient,
) -> None:
    guided = mine(signed, "translations")
    path = f"/threads/{guided['id']}"
    page = shown(signed, f"{path}?into=de")
    assert "not translated yet" in page
    given = submitted(page, f"{path}/edit")
    assert given["into"] == ["de"]
    assert set(entries(given)) == set(into(signed, guided)["sv"])
    assert set(entries(given).values()) == {""}

    typed = {**given, "t.0": ["Hallo"]}
    assert signed.post(f"{path}/edit", data=typed).status_code == 303
    assert list(into(signed, guided)["de"].values()) == ["Hallo"]

    for language in ("svenska!", ""):
        assert signed.get(path, params={"into": language}).status_code == 422


@pytest.mark.slow
def test_translations_left_with_no_language_are_refused(signed: TestClient) -> None:
    guided = mine(signed, "translations")
    path = f"/threads/{guided['id']}"
    given = submitted(shown(signed, path), f"{path}/edit")
    emptied = {**given, **{f"out.{k[2:]}": ["1"] for k in given if k[:2] == "s."}}
    got = signed.post(f"{path}/edit", data=emptied)
    assert got.status_code == 422 and "a language or more" in got.text


@pytest.mark.slow
def test_translations_are_begun_of_a_configuration_s_texts(signed: TestClient) -> None:
    action = "/library/new?kind=translations"
    page = shown(signed, action)
    assert 'name="configuration"' in page and 'name="into"' in page

    lines = mine(signed, "configuration", LINES)
    action += f"&configuration={lines['id']}&into=sv"
    given = submitted(shown(signed, action), action)
    [text] = entries(given)
    written = {**given, "name": ["lines in Swedish"], "t.0": ["Lista diagnoserna."]}
    got = signed.post(action, data={**written, "name": [" "]})
    assert got.status_code == 422
    assert 'name="name" required pattern=".*\\S.*"' in got.text
    got = signed.post(action, data=written)
    assert got.status_code == 303
    made = signed.get(f"/api{got.headers['location']}").json()
    body = signed.get(f"/api/components/{made['head']['digest']}").json()["body"]
    assert body["into"] == {"sv": {text: "Lista diagnoserna."}}

    unread = action.replace(f"configuration={lines['id']}", "configuration=999999")
    assert signed.get(unread).status_code == 422
