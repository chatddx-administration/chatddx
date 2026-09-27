# pyright: basic
"""
What the pages of a record's version share: its fields, a line each; which
of its timeline it is, and what the latest changed of it; whose it is, and
whether the owner reads it; and a value written in a line, as the
inventory writes it.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.db.models import Model
from django.utils.translation import gettext

from chatddx.core import settings
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.names import short_fingerprint
from chatddx.repo.store.branch import (
    AmbiguousBranchError,
    BranchNotFoundError,
    get_visible_branch_model,
)


@dataclass(frozen=True)
class Field:
    """A line of what a record holds: what it is, and its value, or its items."""

    label: Any
    value: str = "—"
    items: list[str] = field(default_factory=list[str])
    # shown as code: a path, a name as it is sent
    code: bool = False
    # shown as it is written, line by line: a template, a prompt
    text: bool = False
    # shown folded, to open: a document too long for the page, a schema
    folded: bool = False
    # a value to look into
    trouble: bool = False


@dataclass(frozen=True)
class Version:
    """Which version of its timeline a row is, and when it was saved."""

    number: int
    of: int
    saved: datetime

    @property
    def latest(self) -> bool:
        return self.number == self.of


@dataclass(frozen=True)
class Change:
    """
    What one version holds in place of what another does, or, of what takes
    more than a line to say, that it changed.
    """

    label: Any
    before: str | None = None
    after: str | None = None


@dataclass(frozen=True)
class Newer:
    """The latest version of a timeline, where the one shown is an earlier."""

    url: str
    version: Version
    changes: list[Change]


def readable(row: BranchModel, identity: str) -> bool:
    """Whether the identity reads the row's timeline: its own, or shared with it."""
    if row.owner.name == identity:
        return True

    return (
        type(row)
        .objects.filter(
            owner_id=row.owner_id, name=row.name, collaborators__name=identity
        )
        .exists()
    )


def timeline_of(row: BranchModel) -> list[Any]:
    """The row's timeline, its first version first."""
    return list(
        type(row)
        .objects.filter(owner_id=row.owner_id, name=row.name)
        .select_related("owner", "trail")
        .order_by("timestamp", "id")
    )


def version_of(row: BranchModel, timeline: list[Any]) -> Version:
    number = next(i for i, each in enumerate(timeline, 1) if each.pk == row.pk)
    return Version(number, len(timeline), row.timestamp)


def branch_of(entity: EntityName, trail: Any, identity: str) -> Any:
    """The newest version of the identity's branch holding `trail`, if it has one."""
    try:
        return get_visible_branch_model(entity, identity, trail=trail.id)
    except (BranchNotFoundError, AmbiguousBranchError):
        return None


def name_of(entity: EntityName, trail: Any, identity: str) -> str:
    """A trail by the name the identity has for it, and its short fingerprint."""
    if trail is None:
        return "—"

    row = branch_of(entity, trail, identity)
    short = short_fingerprint(trail.fingerprint)

    return f"{row.name} ({short})" if row is not None else short


def owner_of(owner: str, identity: str) -> str:
    """Whose a record is, as the identity is told."""
    if owner == identity:
        return gettext("yours")

    if owner == settings.ARCHIVE_IDENTITY_NAME:
        return gettext("the archive's")

    return gettext("%(owner)s's") % {"owner": owner}


def or_none(value: Any) -> str:
    return "—" if value is None or value == "" else str(value)


def said(value: Any) -> str:
    """A value in a line, as the inventory writes it: `name = value, …`."""
    match value:
        case None:
            return "—"
        case bool():
            return "true" if value else "false"
        case dict():
            return ", ".join(f"{k} = {_inner(v)}" for k, v in value.items()) or "{}"
        case list():
            return ", ".join(_inner(item) for item in value)
        case Model():
            return str(value)
        case _:
            return str(value)


def _inner(value: Any) -> str:
    match value:
        case str():
            return json.dumps(value, ensure_ascii=False)
        case dict():
            return "{" + said(value) + "}"
        case list():
            return "[" + said(value) + "]"
        case _:
            return said(value)
