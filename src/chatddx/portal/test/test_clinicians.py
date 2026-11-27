import json
import re
from html import unescape
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from markupsafe import escape

from chatddx.api.test.helpers import family
from chatddx.bench import Bench
from chatddx.catalog import Subject
from chatddx.factors.base import Fingerprint
from chatddx.factors.bundle import Registry
from chatddx.factors.cases import Appendix, Case, Vignette
from chatddx.portal.test.helpers import shown, submitted
from chatddx.store import Catalog, People, Store
from chatddx.store.store import Connection
from chatddx.test.helpers import TYPED


def begun(page: str, kind: str, **given: str) -> str:
    wanted = {"kind": kind, **{f"f.{k}": v for k, v in given.items()}}
    for href in re.findall(r'href="(/library/new\?[^"]*)"', page):
        found = unescape(href)
        if wanted.items() <= dict(parse_qsl(urlsplit(found).query)).items():
            return found
    raise AssertionError(f"no beginning of {kind} given {given}")


def written(signed: TestClient, action: str, **more: str) -> dict[str, Any]:
    got = signed.post(action, data={**submitted(shown(signed, action), action), **more})
    assert got.status_code == 303, got.text[:500]
    return signed.get(f"/api{got.headers['location']}").json()


def body(signed: TestClient, digest: str) -> dict[str, Any]:
    return signed.get(f"/api/components/{digest}").json()["body"]


@pytest.mark.slow
def test_a_case_s_section_shows_its_appendices_and_begins_expectations_only(
    signed: TestClient,
) -> None:
    crlf = family(signed)
    path = f"/cases/{crlf['id']}"
    [default] = signed.get(f"/api/families/{crlf['id']}").json()["cases"]
    given = {"name": "ultrasound", "text": "Gallstones."}
    got = signed.post(f"/api/families/{crlf['id']}/appendices", json=given)
    assert got.status_code == 201
    made = got.json()
    appendices = {"appendices": [made["head"]["digest"]]}
    got = signed.post(f"/api/families/{crlf['id']}/cases", json=appendices)
    assert got.status_code == 201
    case = got.json()
    page = shown(signed, path)
    assert (
        "appendices: ultrasound" in page and f'href="/threads/{made["id"]}"' not in page
    )
    assert "/library/new?kind=appendix" not in page and f"{path}/cases" not in page
    assert signed.post(f"{path}/cases", data={}).status_code == 404

    [expected] = default["expectations"]
    schema = expected["expectation_schema"]
    action = begun(page, "expectation", case=case["case"], expectation_schema=schema)
    page = shown(signed, action)
    assert 'name="f.case"' not in page and 'name="f.data"' in page
    data = json.dumps(expected["data"])
    expecting = written(signed, action, name="with ultrasound", **{"f.data": data})
    held = body(signed, expecting["head"]["digest"])
    assert (held["case"], held["data"]) == (case["case"], expected["data"])
    assert f'href="/threads/{expecting["id"]}">yours</a>' in shown(signed, path)


@pytest.mark.slow
def test_a_case_s_versions_are_its_bindings_and_earlier_cases_offer_a_replacement(
    signed: TestClient, conn: Connection
) -> None:
    noted = family(signed, "noted")
    path = f"/cases/{noted['id']}"
    [case] = signed.get(f"/api/families/{noted['id']}").json()["cases"]
    old = Vignette.model_validate(body(signed, case["case"])["vignette"])
    archive = People(conn).find("archive")
    assert archive is not None
    anew = Fingerprint.of(b"anew")
    _ = Catalog(conn).repair(noted["id"], archive.id, fingerprint=anew)

    registry = Registry()
    labs = registry.add(Appendix(vignette=old, text="Lab: late"))
    late = registry.add(Case(vignette=old, appendices=(labs,)))
    _ = Store(conn).add(registry, [late])

    vignette = signed.get(f"/api/families/{noted['id']}/vignette").json()["text"]
    first = escape(vignette.strip().splitlines()[0])
    page = shown(signed, path)
    assert "Version 2 of 2" in page and anew.hex in page and first not in page
    assert f'href="{path}?version=1"' in page and "/fingerprint/hex" in page

    page = shown(signed, f"{path}?version=1")
    assert "Newer version: version" in page and first not in page
    assert f'value="{late}"' in page
    got = signed.post(f"{path}/replacement", data={"case": late, "version": "1"})
    assert (got.status_code, got.headers["location"]) == (303, f"{path}?version=1")
    page = shown(signed, f"{path}?version=1")
    assert f'value="{late}"' not in page and ">stored</span>" in page
    assert len(signed.get(f"/api/families/{noted['id']}").json()["cases"]) == 2

    got = signed.get(f"{path}?version=3")
    assert got.status_code == 404 and "no version 3 of case" in got.text
    assert first in shown(signed, f"{path}/vignette")


@pytest.mark.slow
def test_what_is_said_of_a_typed_case_is_changed_and_it_is_deleted_and_restored(
    signed: TestClient,
) -> None:
    typed = signed.post(
        "/api/families", json={"text": TYPED, "language": "en", "name": "flight"}
    ).json()
    path = f"/cases/{typed['id']}"
    assert "<h2>Edit</h2>" in shown(signed, path)
    form = {
        "name": "breathless",
        "description": "After a flight.",
        "tags": "b, a",
        "shared": "",
        "language": "sv",
    }
    got = signed.post(f"{path}/said", data=form)
    assert (got.status_code, got.headers["location"]) == (303, path)
    said = signed.get(f"/api{path.replace('cases', 'families')}").json()
    assert (said["name"], said["description"], said["tags"], said["language"]) == (
        "breathless",
        "After a flight.",
        ["a", "b"],
        "sv",
    )

    got = signed.post(f"{path}/said", data={**form, "shared": "nobody-at-all"})
    assert got.status_code == 422 and "no person" in got.text
    got = signed.post(f"{path}/said", data={**form, "name": "", "description": ""})
    assert got.status_code == 303
    said = signed.get(f"/api{path.replace('cases', 'families')}").json()
    assert said["description"] is None and "/" in said["name"]

    assert signed.post(f"{path}/delete").status_code == 303
    page = shown(signed, path)
    assert "You deleted it" in page and "<h2>Edit</h2>" not in page
    assert f'action="{path}/restore"' in shown(signed, "/library?kind=case")
    assert signed.post(f"{path}/restore").status_code == 303
    assert "You deleted it" not in shown(signed, path)

    crlf = family(signed)
    assert "<h2>Edit</h2>" not in shown(signed, f"/cases/{crlf['id']}")
    got = signed.post(f"/cases/{crlf['id']}/said", data=form)
    assert got.status_code == 422 and "of yours" in got.text


@pytest.mark.slow
def test_a_collaborator_leaves_a_case_shared_with_them(
    signed: TestClient, served: FastAPI, conn: Connection
) -> None:
    bob = People(conn).add("bob", "Bob")
    bench = Bench(conn, bob, served.state.chatddx.inventory)
    typed = bench.type_case(TYPED, language="en", name="bob's")
    _ = bench.say(Subject(family=typed.id), collaborators=["alice"])
    path = f"/cases/{typed.id}"
    page = shown(signed, path)
    assert "Shared with you" in page and f'action="{path}/leave"' in page
    got = signed.post(f"{path}/leave")
    assert (got.status_code, got.headers["location"]) == (303, "/library?kind=case")
    assert f'href="{path}"' not in shown(signed, "/library?kind=case")
    assert signed.get(path).status_code == 404

    mine = signed.post("/api/families", json={"text": TYPED, "language": "en"}).json()
    got = signed.post(f"/cases/{mine['id']}/leave")
    assert got.status_code == 422 and "shared with alice" in got.text


@pytest.mark.slow
def test_expectations_shared_with_one_are_taken_for_the_picked_cases(
    signed: TestClient,
) -> None:
    crlf, noted = family(signed), family(signed, "noted")
    [expected] = signed.get(f"/api/families/{crlf['id']}").json()["cases"][0][
        "expectations"
    ]
    query = {"kind": "expectation", "owner": "alice"}
    mine = next(
        t
        for t in signed.get("/api/threads", params=query).json()
        if t["head"]["digest"] == expected["expectation"]
    )
    deleted = signed.patch(f"/api/threads/{mine['id']}", json={"deleted": True})
    assert deleted.status_code == 200
    [shared] = signed.get(f"/api/families/{crlf['id']}").json()["cases"][0][
        "expectations"
    ][0]["shared"]
    page = shown(signed, f"/cases/{crlf['id']}")
    assert f'href="/threads/{shared["id"]}">{shared["owner"]}\'s</a>' in page
    assert 'href="/library" aria-current="page"' in page

    page = shown(signed, "/library?kind=case&tag=swedish")
    assert 'name="tag" value="swedish"' in page
    picked = {"family": [crlf["id"], noted["id"]], "tag": ["swedish"]}
    schema = expected["expectation_schema"]
    got = signed.post(
        "/library/takes", data={**picked, "expectation_schema": schema, "owner": ""}
    )
    assert got.status_code == 200
    [now] = signed.get(f"/api/families/{crlf['id']}").json()["cases"][0]["expectations"]
    taken = signed.get("/api/threads", params=query).json()
    [into] = [t for t in taken if t["head"]["digest"] == now["expectation"]]
    assert f'href="/threads/{into["id"]}">your thread' in got.text
    assert 'href="/library?kind=case&amp;tag=swedish"' in got.text

    got = signed.post("/library/takes", data={"expectation_schema": schema})
    assert got.status_code == 422 and "pick one case or more" in got.text
    assert 'formaction="/library/new"' in got.text
    got = signed.post(
        "/library/takes", data={"family": [0], "expectation_schema": schema}
    )
    assert got.status_code == 404 and "no case 0" in got.text


@pytest.mark.slow
def test_a_case_s_forms_from_another_site_write_nothing(signed: TestClient) -> None:
    elsewhere = {"Sec-Fetch-Site": "cross-site"}
    for action in ("said", "delete", "restore", "leave", "replacement"):
        assert signed.post(f"/cases/1/{action}", headers=elsewhere).status_code == 403
    assert signed.post("/library/takes", headers=elsewhere).status_code == 403
