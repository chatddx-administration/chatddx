from pathlib import Path

import pytest
import pytest_asyncio

from chatddx.core.models import IdentityModel, TagModel
from chatddx.repo.shufflers.cases import dump_cases_async
from chatddx.repo.shufflers.main import ensure_identity_async
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

    dumped = await dump_case_tags_async(tags_path, case_branches, owner.name)

    assert {tag.name for tag in dumped["case-alpha"]} == {"respiratory", "fever"}
    assert {tag.name for tag in dumped["case-beta"]} == {"abdominal"}

    fever_branches = await load_case_branches_by_tag_async("fever", owner.name)
    assert [b.name for b in fever_branches] == ["case-alpha"]

    abdominal_branches = await load_case_branches_by_tag_async("abdominal", owner.name)
    assert [b.name for b in abdominal_branches] == ["case-beta"]

    none_branches = await load_case_branches_by_tag_async("no-such-tag", owner.name)
    assert none_branches == []


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_tags_are_owner_scoped(owner: IdentityModel):
    other_owner = await ensure_identity_async("olof")

    cases_dir = Path(__file__).parent / "data/cases"
    tags_path = Path(__file__).parent / "data/tags.toml"

    case_branches = await dump_cases_async(cases_dir, owner.name)
    other_case_branches = await dump_cases_async(cases_dir, other_owner.name)

    await dump_case_tags_async(tags_path, case_branches, owner.name)
    await dump_case_tags_async(tags_path, other_case_branches, other_owner.name)

    fever_tags = [tag async for tag in TagModel.objects.filter(name="fever")]
    assert {tag.owner_id for tag in fever_tags} == {owner.pk, other_owner.pk}

    fever_branches = await load_case_branches_by_tag_async("fever", owner.name)
    assert [b.owner_id for b in fever_branches] == [owner.pk]

    other_fever_branches = await load_case_branches_by_tag_async(
        "fever", other_owner.name
    )
    assert [b.owner_id for b in other_fever_branches] == [other_owner.pk]
