# src/chatddx/repo/shufflers/tags.py

import tomllib
from pathlib import Path

from chatddx.core.models import TagModel
from chatddx.repo.base import BranchModel
from chatddx.repo.branch_models import CaseBranchModel
from chatddx.repo.shufflers.main import ensure_identity, qs_canon
from chatddx.utils import make_async


def parse_case_tags(tags_path: Path) -> dict[str, list[str]]:
    """Read the case -> tag-names mapping out of a tags TOML file."""
    data = tomllib.loads(tags_path.read_text(encoding="utf-8"))

    return {
        case_name: list(entry.get("tags", []))
        for case_name, entry in data.get("case", {}).items()
    }


def dump_case_tags(
    tags_path: Path,
    case_branches: dict[int, BranchModel],
    owner_name: str,
) -> dict[str, list[TagModel]]:
    owner = ensure_identity(owner_name)
    case_tags = parse_case_tags(tags_path)
    branches_by_name = {branch.name: branch for branch in case_branches.values()}

    dumped_tags: dict[str, list[TagModel]] = {}

    for case_name, tag_names in case_tags.items():
        branch = branches_by_name.get(case_name)
        if branch is None:
            continue

        tags = [
            TagModel.objects.get_or_create(name=tag_name, owner=owner)[0]
            for tag_name in tag_names
        ]
        branch.tags.set(tags)  # pyright: ignore[reportAttributeAccessIssue]
        dumped_tags[case_name] = tags

    return dumped_tags


dump_case_tags_async = make_async(dump_case_tags)


def load_case_branches_by_tag(
    tag_name: str,
    owner_name: str,
) -> list[CaseBranchModel]:
    qs = CaseBranchModel.objects.filter(
        tags__name=tag_name, tags__owner__name=owner_name
    )
    return list(qs_canon(qs, owner_name))


load_case_branches_by_tag_async = make_async(load_case_branches_by_tag)
