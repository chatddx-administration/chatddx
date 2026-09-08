from pathlib import Path

import pytest
import pytest_asyncio

from chatddx.core.models import IdentityModel
from chatddx.repo.shufflers.main import dump_cases_async, ensure_identity_async
from chatddx.repo.shufflers.tags import (
    dump_case_tags_async,
    load_case_branches_by_tag_async,
    parse_case_tags,
)


@pytest_asyncio.fixture
async def owner():
    return await ensure_identity_async("alex")


@pytest.mark.django_db
def test_parse_case_tags():
    tags_path = Path(__file__).parent / "data/tags.toml"

    case_tags = parse_case_tags(tags_path)

    assert case_tags == {
        "case-alpha": ["respiratory", "fever"],
        "case-beta": ["abdominal"],
    }


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_dump_case_tags_and_lookup(owner: IdentityModel):
    cases_dir = Path(__file__).parent / "data/cases"
    tags_path = Path(__file__).parent / "data/tags.toml"

    case_branches = await dump_cases_async(cases_dir, owner.name)

    dumped = await dump_case_tags_async(tags_path, case_branches)

    assert {tag.name for tag in dumped["case-alpha"]} == {"respiratory", "fever"}
    assert {tag.name for tag in dumped["case-beta"]} == {"abdominal"}

    fever_branches = await load_case_branches_by_tag_async("fever", owner.name)
    assert [b.name for b in fever_branches] == ["case-alpha"]

    abdominal_branches = await load_case_branches_by_tag_async("abdominal", owner.name)
    assert [b.name for b in abdominal_branches] == ["case-beta"]

    none_branches = await load_case_branches_by_tag_async("no-such-tag", owner.name)
    assert none_branches == []
