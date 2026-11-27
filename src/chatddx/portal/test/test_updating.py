import pytest
from fastapi.testclient import TestClient

from chatddx.api.test.helpers import thread
from chatddx.bench import Bench
from chatddx.bench.test.helpers import move_model
from chatddx.catalog import threads
from chatddx.portal.test.helpers import said, shown, submitted
from chatddx.store import People
from chatddx.test.helpers import alices_bench
from chatddx.test.world import (
    GPT_OSS_ARTIFACT,
    GPT_OSS_MODEL,
    LINES,
    QWEN_ARTIFACT,
    QWEN_MODEL,
)

__all__ = ["alices_bench"]


@pytest.mark.slow
def test_what_is_out_of_date_is_tagged_and_updated_one_by_one_or_all(
    signed: TestClient, bench: Bench
) -> None:
    theirs = thread(signed, "judge", "verdict", "archive")
    mine = bench.fork(theirs["id"], "my-verdict").edit.thread
    bench.conn.commit()
    configuration = thread(signed, "configuration", LINES)
    assert not configuration["outdated"]
    assert "Update all" not in said(shown(signed, "/library"))

    _ = move_model(bench, QWEN_ARTIFACT, revision="moved")
    bench.conn.commit()
    assert thread(signed, "configuration", LINES)["outdated"]
    library = said(shown(signed, "/library?kind=configuration"))
    assert "Out of date" in library and "Update all" in library
    lab = said(shown(signed, f"/compose/{configuration['id']}"))
    assert f"Its model, {QWEN_MODEL}, has a new version." in lab
    assert "Can't be used." in lab
    scoring = said(shown(signed, f"/scoring/{mine}"))
    assert f"Its model, {QWEN_MODEL}, has a new version." in scoring
    read_only = shown(signed, f"/threads/{theirs['id']}")
    assert "Out of date" in said(read_only)
    assert f"/threads/{theirs['id']}/update" not in read_only

    page = shown(signed, f"/threads/{mine}")
    form = submitted(page, f"/threads/{mine}/update")
    got = signed.post(
        f"/threads/{mine}/update", data={k: v[0] for k, v in form.items()}
    )
    assert (got.status_code, got.headers["location"]) == (303, f"/threads/{mine}")
    assert not thread(signed, "judge", "my-verdict")["outdated"]
    assert "Out of date" not in said(shown(signed, f"/threads/{mine}"))

    done = signed.post("/library/update")
    assert done.status_code == 200, done.text[:500]
    updated = said(done.text)
    assert LINES in updated and "my-verdict" not in updated
    assert "Not updated" not in updated
    assert not thread(signed, "configuration", LINES)["outdated"]
    assert "Update all" not in said(shown(signed, "/library"))


@pytest.mark.slow
def test_a_world_s_switch_of_model_is_named_and_updated_all_at_once(
    signed: TestClient, bench: Bench
) -> None:
    archive = People(bench.conn).find("archive")
    assert archive is not None
    theirs = Bench(bench.conn, archive, bench.inventory)
    origin = theirs.thread(LINES, "configuration")[0].thread
    mine = thread(signed, "configuration", LINES)
    assert "Update all" not in said(shown(signed, "/library"))

    gpt_oss = bench.handle_named(GPT_OSS_ARTIFACT).weights
    switched = theirs.variation(origin, {"model": gpt_oss})
    _ = theirs.edit(origin, threads.head(bench.rows, origin).id, switched)
    bench.conn.commit()
    assert "Update all" in said(shown(signed, "/library"))
    named = (
        f"Its origin is now made for {GPT_OSS_MODEL}, where yours is made for "
        + f"{QWEN_MODEL}: updating moves yours to {GPT_OSS_MODEL}."
    )
    assert named in said(shown(signed, f"/threads/{mine['id']}"))
    assert named in said(shown(signed, f"/compose/{mine['id']}"))

    done = signed.post("/library/update")
    assert done.status_code == 200, done.text[:500]
    followed = said(done.text)
    assert LINES in followed
    assert f"now made for {GPT_OSS_MODEL}, was {QWEN_MODEL}" in followed
    assert "Not updated" not in followed
    assert "Update all" not in said(shown(signed, "/library"))
