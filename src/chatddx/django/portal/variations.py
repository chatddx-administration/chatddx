# pyright: basic
"""
A slice's variation as its page edits it, whichever the slice: its
timeline; what saving the page under a name does, a new version of it or a
new variation; the other variations holding what the page would save; what
of the owner's goes by its name, their configurations, their runs and their
batches' trials; and deleting it, where nothing does.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from django.db import transaction
from django.utils.translation import gettext

from chatddx.bench.bench import Bench
from chatddx.bench.cell import NONE
from chatddx.django.portal.configurations import page_of as configuration_page
from chatddx.history.models import RunModel
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entity_names import EntityName
from chatddx.repo.queries import head_of, qs_head
from chatddx.worker.models import JobModel

# what a variation's name can't hold: what parts an owner from a name, and
# what parts a cell's label and a trial's description
HELD_APART = ("/", "+", "=", "×")


def versions_of(entity: EntityName, owner: str, name: str) -> list[Any]:
    """The owner's variation of the name: its timeline, the first version first."""
    return list(
        entity_of(entity)
        .branch_model.objects.filter(owner__name=owner, name=name)
        .select_related("owner", "trail")
        .order_by("timestamp", "id")
    )


def refused(name: str) -> str | None:
    """Why a variation can't go by `name`, if it can't."""
    for apart in HELD_APART:
        if apart in name:
            return gettext(
                "A name can't hold '%(apart)s': the portal and the repl part names "
                + "and cells by it."
            ) % {"apart": apart}

    if name.lower() == NONE:
        return gettext("A variation can't be called none: it takes a toolset out.")

    return None


class Saving(StrEnum):
    # a new version of the variation the page is of
    SAME = "same"
    # a new variation, the page's own staying as it is
    NEW = "new"
    # the name of another variation of the owner's: not saved over
    TAKEN = "taken"


@dataclass(frozen=True)
class Said:
    """What saving the page under a name does, said before it is done."""

    saving: Saving
    name: str
    # the version the save makes of the variation it saves to
    version: int
    # the version the page began from, where it is an earlier one
    since: int | None = None
    # the page's variation, where it is of one
    edited: str | None = None
    # why the name can't be one, where it can't
    why: str | None = None
    # the head of the other variation the name is taken by
    taken: Any = None
    # whether the latest version holds what the page would save already
    unchanged: bool = False

    @property
    def saves(self) -> bool:
        return bool(self.name) and self.why is None and self.saving != Saving.TAKEN

    @property
    def line(self) -> str:
        said = {"name": self.name, "version": self.version, "since": self.since}

        match self.saving:
            case _ if not self.name:
                return gettext("Name the variation to save it.")
            case _ if self.why is not None:
                return self.why
            case Saving.TAKEN:
                return (
                    gettext(
                        "%(name)s is another variation of yours: open it to change it, "
                        + "or name this one otherwise."
                    )
                    % said
                )
            case Saving.SAME if self.unchanged:
                return gettext(
                    "Nothing to save: the latest version holds this already."
                )
            case Saving.SAME if self.since is not None:
                return (
                    gettext(
                        "Saving makes version %(version)d of this variation, from "
                        + "version %(since)d."
                    )
                    % said
                )
            case Saving.SAME:
                return (
                    gettext("Saving makes version %(version)d of this variation.")
                    % said
                )
            case Saving.NEW if self.edited is not None:
                return (
                    gettext(
                        "Saving makes a new variation, %(name)s, and this one stays "
                        + "as it is."
                    )
                    % said
                )
            case Saving.NEW:
                return gettext("Saving makes a new variation, %(name)s.") % said

    @property
    def button(self) -> str:
        match self.saving:
            case Saving.SAME if self.saves and not self.unchanged:
                return gettext("Save as version %(version)d") % {
                    "version": self.version
                }
            case Saving.NEW if self.saves:
                return gettext("Save as a new variation")
            case _:
                return gettext("Save")


def said(
    entity: EntityName,
    owner: str,
    name: str,
    edited: str | None = None,
    since: int | None = None,
    fingerprint: str | None = None,
) -> Said:
    """
    What saving under `name` does, the page being of `edited` where it is,
    and holding what comes to `fingerprint`, where that is known.
    """
    name = name.strip()
    why = refused(name) if name else None
    rows = entity_of(entity).branch_model.objects.filter(owner__name=owner)
    count = rows.filter(name=name).count() if name else 0
    head = head_of(rows, owner, name) if count else None

    if edited is not None and name == edited:
        unchanged = (
            head is not None
            and fingerprint is not None
            and head.trail.fingerprint == fingerprint
        )
        return Said(Saving.SAME, name, count + 1, since, edited, why, None, unchanged)

    if head is None:
        return Said(Saving.NEW, name, 1, None, edited, why)

    return Said(Saving.TAKEN, name, count + 1, None, edited, why, head)


@dataclass(frozen=True)
class Sharer:
    """Another variation whose latest version holds what the page would save."""

    name: str
    owner: str
    pk: int
    own: bool


def sharers(
    entity: EntityName,
    owner: str,
    fingerprint: str,
    name: str,
    edited: str | None = None,
) -> list[Sharer]:
    """
    The variations, the owner's own and those shared with them, whose head
    holds what comes to `fingerprint`, bar the page's own and the one it
    saves to: a shared one named as the page names its variation gives way
    to it.
    """
    trail = (
        entity_of(entity)
        .trail_model.objects.filter(fingerprint=fingerprint)
        .values_list("pk", flat=True)
        .first()
    )

    if trail is None:
        return []

    return [
        Sharer(head.name, head.owner.name, head.pk, head.owner.name == owner)
        for head in Bench(owner).visible(entity)
        if head.trail_id == trail
        and head.name != name
        and not (head.owner.name == owner and head.name == edited)
    ]


@dataclass(frozen=True)
class Holding:
    """A configuration of the owner's whose latest version holds the variation."""

    name: str
    page: str
    # the version of the variation it holds
    version: int


@dataclass(frozen=True)
class Holds:
    """
    What of the owner's goes by the variation's name: their configurations,
    those whose latest version holds a version of it and how many earlier
    versions do; their runs; and their batches' trials that set it. What
    holds a version another variation of theirs holds too goes by that one's
    name as much, and is not the variation's alone.
    """

    configurations: list[Holding] = field(default_factory=list[Holding])
    earlier: int = 0
    runs: int = 0
    trials: int = 0

    @property
    def anything(self) -> bool:
        return bool(self.configurations or self.earlier or self.runs or self.trials)


def holds_of(entity: EntityName, owner: str, rows: list[Any]) -> Holds:
    """What of the owner's goes by the name of the variation whose timeline `rows` is."""
    if not rows:
        return Holds()

    name = rows[-1].name
    numbers = {row.trail_id: number for number, row in enumerate(rows, 1)}
    # the versions no other variation of the owner's holds
    alone = set(numbers) - set(
        entity_of(entity)
        .branch_model.objects.filter(owner__name=owner, trail_id__in=numbers)
        .exclude(name=name)
        .values_list("trail_id", flat=True)
    )
    held = {f"trail__{entity}_id__in": alone}
    configurations = ConfigurationBranchModel.objects.filter(owner__name=owner)
    heads = {head.pk for head in qs_head(configurations, owner)}
    holding = list(
        configurations.filter(**held).select_related("trail").order_by("name")
    )

    return Holds(
        configurations=[
            Holding(
                row.name,
                configuration_page(row.pk),
                numbers[getattr(row.trail, f"{entity}_id")],
            )
            for row in holding
            if row.pk in heads
        ],
        earlier=sum(1 for row in holding if row.pk not in heads),
        runs=RunModel.objects.filter(
            owner__name=owner, **{f"trial__configuration__{entity}_id__in": alone}
        ).count(),
        trials=JobModel.objects.filter(
            owner__name=owner, **{f"set__{entity}": name}
        ).count(),
    )


def delete_variation(entity: EntityName, owner: str, name: str) -> bool:
    """
    The owner's variation of the name gone for good, every version of it,
    where nothing of theirs goes by its name; and else left as it is.
    """
    with transaction.atomic():
        rows = versions_of(entity, owner, name)

        if not rows or holds_of(entity, owner, rows).anything:
            return False

        _ = (
            entity_of(entity)
            .branch_model.objects.filter(pk__in=[row.pk for row in rows])
            .delete()
        )

        return True
