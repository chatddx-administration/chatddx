import pytest
from fastapi.testclient import TestClient

from chatddx import settings
from chatddx.test.helpers import TYPED


def test_a_typed_case_is_a_family_of_one_s_own_with_its_vignette(
    signed: TestClient, bob: dict[str, str]
) -> None:
    got = signed.post(
        "/api/families", json={"text": TYPED, "name": "flight", "language": "en"}
    )
    assert got.status_code == 201
    made = got.json()
    assert got.headers["location"] == f"/api/families/{made['id']}"
    assert (made["name"], made["owner"], made["language"]) == ("flight", "alice", "en")
    vignette = signed.get(f"/api/families/{made['id']}/vignette").json()
    assert (vignette["source"], vignette["text"], vignette["drifted"]) == (
        "typed",
        TYPED,
        False,
    )
    assert signed.get(f"/api/families/{made['id']}", headers=bob).status_code == 404


@pytest.mark.slow
def test_what_can_t_be_typed_is_refused_and_a_day_s_quota_held(
    signed: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for asked, said in (
        ({"text": " "}, "a typed case holds text"),
        ({"text": "a\u0000b"}, "U+0000"),
        ({"text": TYPED, "source": "test"}, "'test' isn't a database source"),
        ({"text": TYPED, "language": "Swedish"}, "'Swedish' is not a language tag"),
    ):
        got = signed.post("/api/families", json={"language": "en", **asked})
        assert got.status_code == 422, (asked, got.json())
        assert said in got.json()["detail"]

    got = signed.post("/api/families", json={"text": TYPED})
    assert (got.status_code, got.json()["detail"][0]["loc"]) == (
        422,
        ["body", "language"],
    )
    monkeypatch.setattr(settings, "TYPED_PER_DAY", 1)
    typed = {"text": TYPED, "language": "sv"}
    assert signed.post("/api/families", json=typed).status_code == 201
    got = signed.post("/api/families", json=typed)
    assert got.status_code == 429
    assert "over the day's quota" in got.json()["detail"]
