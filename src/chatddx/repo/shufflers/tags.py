# src/chatddx/repo/shufflers/tags.py
"""Wiring for case tags.

Tags are not repo-matter: a tag is a plain `TagModel` row plus a
many-to-many relation on `CaseBranchModel`, with no trail/branch pair of
its own and no central tag-management surface. They exist so a case branch
can be found by one or more short labels, and so the trail currently
associated with each tagged case can be looked up through them.
"""

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
    """Attach the tags in `tags_path` to the given, already-dumped case branches.

    `case_branches` is the mapping `dump_cases()` returns (branch pk ->
    branch), so branches that were just dumped can be tagged without
    another database round trip to look them up by name. Tags are
    owner-scoped (see TagModel), so `owner_name` -- the same owner
    `case_branches` were dumped under -- is used both to look up and to
    create them.
    """
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
    """Return the trail currently associated with each case tagged `tag_name`.

    A case branch may have several historical versions; this resolves, per
    case name owned by `owner_name`, only the one currently canonical --
    i.e. the trail the case's tag should be understood to point at. Tags
    are owner-scoped, so this only ever matches `owner_name`'s own
    `tag_name` tag, never another owner's tag of the same name.
    """
    qs = CaseBranchModel.objects.filter(
        tags__name=tag_name, tags__owner__name=owner_name
    )
    return list(qs_canon(qs, owner_name))


load_case_branches_by_tag_async = make_async(load_case_branches_by_tag)
