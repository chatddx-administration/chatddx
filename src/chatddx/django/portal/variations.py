# pyright: basic
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

HELD_APART = ("/", "+", "=", "×")


def versions_of(entity: EntityName, owner: str, name: str) -> list[Any]:
    return list(
        entity_of(entity)
        .branch_model.objects.filter(owner__name=owner, name=name)
        .select_related("owner", "trail")
        .order_by("timestamp", "id")
    )


def refused(name: str) -> str | None:
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
    SAME = "same"
    NEW = "new"
    TAKEN = "taken"


@dataclass(frozen=True)
class Said:
    saving: Saving
    name: str
    version: int
    since: int | None = None
    edited: str | None = None
    why: str | None = None
    taken: Any = None
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
    name: str
    page: str
    version: int


@dataclass(frozen=True)
class Holds:
    configurations: list[Holding] = field(default_factory=list[Holding])
    earlier: int = 0
    runs: int = 0
    trials: int = 0

    @property
    def anything(self) -> bool:
        return bool(self.configurations or self.earlier or self.runs or self.trials)


def holds_of(entity: EntityName, owner: str, rows: list[Any]) -> Holds:
    if not rows:
        return Holds()

    name = rows[-1].name
    numbers = {row.trail_id: number for number, row in enumerate(rows, 1)}
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
