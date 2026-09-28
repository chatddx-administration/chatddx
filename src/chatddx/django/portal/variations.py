# pyright: basic
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.utils.translation import gettext

from chatddx.bench.cell import NONE
from chatddx.bench.held import held
from chatddx.django.portal.configurations import page_of as configuration_page
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entity_names import EntityName
from chatddx.repo.queries import qs_head
from chatddx.repo.store.timeline import select_versions

HELD_APART = ("/", "+", "=", "×")


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
    found = held(owner, entity, alone)
    heads = {
        head.pk
        for head in qs_head(
            ConfigurationBranchModel.objects.filter(owner__name=owner), owner
        )
    }

    return Holds(
        configurations=[
            Holding(
                row.name,
                configuration_page(row.pk),
                numbers[getattr(row.trail, f"{entity}_id")],
            )
            for row in found.configurations
            if row.pk in heads
        ],
        earlier=sum(1 for row in found.configurations if row.pk not in heads),
        runs=found.runs,
        trials=found.jobs,
    )


def delete_variation(entity: EntityName, owner: str, name: str) -> bool:
    with transaction.atomic():
        rows = select_versions(entity, owner, name)

        if not rows or holds_of(entity, owner, rows).anything:
            return False

        _ = (
            entity_of(entity)
            .branch_model.objects.filter(pk__in=[row.pk for row in rows])
            .delete()
        )

        return True
