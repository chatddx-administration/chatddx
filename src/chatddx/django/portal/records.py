# pyright: basic

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from django.db.models import Model, prefetch_related_objects
from django.utils.translation import gettext

from chatddx.core import settings
from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.names import short_fingerprint
from chatddx.repo.store.branch import branch_named, holders_of
from chatddx.repo.store.timeline import alike, saving, select_versions


@dataclass(frozen=True)
class Field:
    label: Any
    value: str = "—"
    items: list[str] = field(default_factory=list[str])
    code: bool = False
    text: bool = False
    folded: bool = False
    trouble: bool = False


@dataclass(frozen=True)
class Version:
    number: int
    of: int
    saved: datetime

    @property
    def latest(self) -> bool:
        return self.number == self.of


@dataclass(frozen=True)
class Change:
    label: Any
    before: str | None = None
    after: str | None = None
    words: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    whole: bool = False


@dataclass(frozen=True)
class Newer:
    url: str
    version: Version
    changes: list[Change]


def timeline_of(row: BranchModel) -> list[Any]:
    return select_versions(
        entity_of(row).name, row.owner.name, row.name, model=type(row)
    )


def version_of(row: BranchModel, timeline: list[Any]) -> Version:
    number = next(i for i, each in enumerate(timeline, 1) if each.pk == row.pk)
    return Version(number, len(timeline), row.timestamp)


def name_of(entity: EntityName, trail: Any, identity: str) -> str:
    if trail is None:
        return "—"

    short = short_fingerprint(trail.fingerprint)
    named = branch_named(entity, identity, trail)

    return f"{named} ({short})" if named is not None else short


def owner_of(owner: str, identity: str) -> str:
    if owner == identity:
        return gettext("yours")

    if owner == settings.ARCHIVE_IDENTITY_NAME:
        return gettext("the archive's")

    return gettext("%(owner)s's") % {"owner": owner}


def or_none(value: Any) -> str:
    return "—" if value is None or value == "" else str(value)


def said(value: Any) -> str:
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


class Saving(StrEnum):
    SAME = "same"
    NEW = "new"
    ONTO = "onto"
    BACK = "back"


@dataclass(frozen=True)
class Said:
    saving: Saving
    name: str
    version: int
    what: str
    content: str = ""
    replaces: bool = False
    onto: Any = None
    since: int | None = None
    edited: str | None = None
    why: str | None = None
    capitals: list[str] = field(default_factory=list[str])
    unchanged: bool = False

    @property
    def taken(self) -> bool:
        return not self.replaces and self.saving in (Saving.ONTO, Saving.BACK)

    @property
    def saves(self) -> bool:
        return bool(self.name) and self.why is None and not self.taken

    @property
    def line(self) -> str:
        said = {
            "name": self.name,
            "version": self.version,
            "since": self.since,
            "what": self.what,
            "content": self.content,
        }

        if not self.name:
            return gettext("Name the %(what)s to save it.") % said

        if self.why is not None:
            return self.why

        if self.taken:
            return (
                gettext(
                    "%(name)s is another %(what)s of yours: open it to change it, "
                    + "or name this one otherwise."
                )
                % said
            )

        match self.saving:
            case Saving.SAME if self.unchanged:
                return gettext(
                    "Nothing to save: the latest version holds this already."
                )
            case Saving.SAME if self.since is not None:
                return (
                    gettext(
                        "Saving makes version %(version)d of this %(what)s, from "
                        + "version %(since)d."
                    )
                    % said
                )
            case Saving.SAME:
                return (
                    gettext("Saving makes version %(version)d of this %(what)s.") % said
                )
            case Saving.NEW if self.edited is not None:
                return (
                    gettext(
                        "Saving makes a new %(what)s, %(name)s, and this one stays "
                        + "as it is."
                    )
                    % said
                )
            case Saving.NEW:
                return gettext("Saving makes a new %(what)s, %(name)s.") % said
            case Saving.ONTO:
                return (
                    gettext(
                        "Saving makes version %(version)d of %(name)s, another "
                        + "%(what)s of yours, replacing %(content)s."
                    )
                    % said
                )
            case Saving.BACK:
                return (
                    gettext(
                        "Saving brings back %(name)s, which you deleted, as its "
                        + "version %(version)d, replacing %(content)s."
                    )
                    % said
                )

    @property
    def button(self) -> str:
        said = {"name": self.name, "version": self.version, "what": self.what}

        match self.saving:
            case Saving.SAME if self.saves and not self.unchanged:
                return gettext("Save as version %(version)d") % said
            case Saving.NEW if self.saves:
                return gettext("Save as a new %(what)s") % said
            case Saving.ONTO if self.saves:
                return gettext("Save onto %(name)s…") % said
            case Saving.BACK if self.saves:
                return gettext("Bring %(name)s back…") % said
            case _:
                return gettext("Save")


def said_of(
    entity: EntityName,
    owner: str,
    name: str,
    what: str,
    content: str = "",
    replaces: bool = False,
    edited: str | None = None,
    since: int | None = None,
    fingerprint: str | None = None,
    why: str | None = None,
) -> Said:
    name = name.strip()

    if not name:
        return Said(
            Saving.NEW, name, 1, what, content, replaces, edited=edited, why=why
        )

    save = saving(entity, owner, name, fingerprint)
    capitals = [other for other in alike(entity, owner, name) if other != edited]
    told = {"edited": edited, "why": why, "capitals": capitals}

    if edited is not None and name == edited:
        return Said(
            Saving.SAME,
            name,
            save.version,
            what,
            content,
            replaces,
            since=since,
            unchanged=save.unchanged,
            **told,
        )

    if save.head is None:
        return Said(Saving.NEW, name, 1, what, content, replaces, **told)

    return Said(
        Saving.BACK if save.deleted else Saving.ONTO,
        name,
        save.version,
        what,
        content,
        replaces,
        onto=save.head,
        **told,
    )


@dataclass(frozen=True)
class Sharer:
    name: str
    owner: str
    pk: int
    own: bool
    tagged: bool = False


def sharers(
    entity: EntityName,
    owner: str,
    fingerprint: str,
    name: str,
    edited: str | None = None,
) -> list[Sharer]:
    holders = holders_of(entity, owner, fingerprint)
    prefetch_related_objects(holders, "tags")

    return [
        Sharer(
            holder.name,
            holder.owner.name,
            holder.pk,
            holder.owner.name == owner,
            bool(list(holder.tags.all())),
        )
        for holder in holders
        if holder.name != name
        and not (holder.owner.name == owner and holder.name == edited)
    ]
