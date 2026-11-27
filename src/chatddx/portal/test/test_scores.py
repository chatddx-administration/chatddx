import re

import pytest
from fastapi.testclient import TestClient

from chatddx.portal import judged
from chatddx.portal.test.helpers import settled, shown, started, world_served

__all__ = ["world_served"]

_LINK = re.compile(r'href="(/scores/[^/"]+/[^/"]+/\d+/\d+)"')


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_score_on_the_run_page_leads_to_what_its_metric_read(
    signed: TestClient,
) -> None:
    run = started(signed)
    _ = settled(signed, run)
    links = _LINK.findall(shown(signed, f"/runs/{run}"))
    assert links
    for link in links:
        page = shown(signed, link)
        assert "<h2>Reading</h2>" in page or "<h2>Verdict</h2>" in page, link
        assert "Scored again now" not in page, link


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_score_links_to_its_repeats_both_ways(signed: TestClient) -> None:
    three = started(signed, seeds=[11, 12, 13])
    one = started(signed, seeds=[13])
    for run in (three, one):
        _ = settled(signed, run)
    first, *_ = signed.get(f"/api/runs/{three}/scores").json()
    [again] = [
        g
        for g in signed.get(f"/api/runs/{one}/scores").json()
        if g["scorer"] == first["scorer"]
    ]
    [case] = {i["case"] for i in first["items"]}
    third = f"/scores/{first['score']}/{case}/2/0"
    fourth = f"/scores/{again['score']}/{case}/0/0"

    page = shown(signed, third)
    assert f'href="{fourth}"' in page and f'href="/runs/{one}"' in page
    assert f'href="{third}"' in shown(signed, fourth)
    unrepeated = shown(signed, f"/scores/{first['score']}/{case}/0/0")
    assert "None yet." in unrepeated and f'href="/runs/{one}"' not in unrepeated


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_judged_score_shows_what_its_judge_was_asked_and_decided(
    signed: TestClient,
) -> None:
    [noted] = signed.get("/api/families", params={"name": "noted"}).json()
    run = started(signed, families=[noted["id"]])
    _ = settled(signed, run)
    links = [
        f"/scores/{g['score']}/{d['case']}/{d['replicate']}/{d['view']}"
        for g in signed.get(f"/api/runs/{run}/scores").json()
        for d in signed.get(f"/api/runs/{run}/scores/{g['score']}/items").json()[
            "items"
        ]
        if d["judge_calls"]
    ]
    assert links
    for link in links:
        page = shown(signed, link)
        assert "<h3>Answer</h3>" in page and "Seed " in page, link
        assert "Rebuilt now" not in page and "Scored again now" not in page, link
        assert "<mark" in page, link


@pytest.mark.usefixtures("fake")
def test_a_judge_s_request_rebuilt_otherwise_than_sent_is_told(
    signed: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    [noted] = signed.get("/api/families", params={"name": "noted"}).json()
    run = started(signed, families=[noted["id"]])
    _ = settled(signed, run)
    [link, *_] = [
        f"/scores/{g['score']}/{d['case']}/{d['replicate']}/{d['view']}"
        for g in signed.get(f"/api/runs/{run}/scores").json()
        for d in signed.get(f"/api/runs/{run}/scores/{g['score']}/items").json()[
            "items"
        ]
        if d["judge_calls"]
    ]

    def otherwise(_: object) -> None:
        return None

    monkeypatch.setattr(judged, "fingerprint_request", otherwise)
    assert "Rebuilt now" in shown(signed, link)
