# pyright: basic
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from django.urls import reverse

from chatddx.bench.bench import Bench
from chatddx.bench.cell import NONE, SLICES, Cell
from chatddx.core import settings
from chatddx.django.portal.records import (
    Change,
    Field,
    Newer,
    Version,
    branch_of,
    name_of,
    owner_of,
    readable,
    timeline_of,
    version_of,
)
from chatddx.django.portal.slices import LABELS, done, fields_of, page_of_variation
from chatddx.history.models import RunModel
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entity_names import EntityName
from chatddx.repo.names import short_fingerprint
from chatddx.repo.store.branch import AmbiguousBranchError, BranchNotFoundError
from chatddx.repo.utils import resolve_trail
from chatddx.worker.models import JobModel

_SET = re.compile(r"\+(" + "|".join(SLICES) + r")=([^+]*)$")


@dataclass(frozen=True)
class Slice:
    entity: str
    label: Any
    name: str
    fingerprint: str | None
    fields: list[Field]
    own: str | None = None
    changes: list[Change] = field(default_factory=list[Change])
    version: Version | None = None
    newer: Newer | None = None
    page: str | None = None

    @property
    def set(self) -> bool:
        return self.own is not None


@dataclass(frozen=True)
class Shown:
    row: ConfigurationBranchModel
    cell: Cell
    label: str
    owner: str
    fingerprint: str
    version: Version
    before: str | None
    after: str | None
    newer: Newer | None
    slices: list[Slice]
    varies: str | None

    @property
    def set(self) -> list[Slice]:
        return [each for each in self.slices if each.set]


def page_of(row: int, pins: Mapping[str, int | str] | None = None) -> str:
    url = reverse("admin:portal_configuration_change", args=[row])
    pinned = pins or {}
    query = urlencode(
        [(entity, pinned[entity]) for entity in SLICES if entity in pinned]
    )

    return f"{url}?{query}" if query else url


def page_named(
    identity: str, configuration: str, set_names: Mapping[str, str] | None = None
) -> str | None:
    bench = Bench(identity)

    named = set_names or {}

    try:
        row = bench.configuration_named(configuration)
        pins: dict[str, int | str] = {
            entity: NONE
            if named[entity] == NONE
            else bench.variation_named(entity, named[entity]).id
            for entity in SLICES
            if entity in named
        }
    except (BranchNotFoundError, AmbiguousBranchError):
        return None

    return page_of(row.pk, pins)


def page_of_run(run: RunModel, job: JobModel | None = None) -> str | None:
    identity = run.owner.name
    trial = run.trial.configuration
    job = job or JobModel.objects.filter(run=run).first()
    entities: list[EntityName] = []

    if job is not None:
        name = job.configuration
        entities = [entity for entity in SLICES if entity in job.set]
    else:
        description = run.conversation.description if run.conversation else ""
        name, entities = (
            parsed(description.split(" × ")[0]) if description else ("", [])
        )

    base = _base(identity, name, entities, trial) if name else None

    if base is None:
        held = branch_of("configuration", trial, identity)
        return None if held is None else page_of(held.pk)

    pins: dict[str, int | str] = {}

    for entity in entities:
        variation = getattr(trial, entity)

        if variation is None:
            pins[entity] = NONE
            continue

        row = branch_of(entity, variation, identity)

        if row is None:
            return page_of(base.pk)

        pins[entity] = row.pk

    return page_of(base.pk, pins)


def parsed(label: str) -> tuple[str, list[EntityName]]:
    named: list[str] = []

    while (found := _SET.search(label)) is not None:
        named.insert(0, found.group(1))
        label = label[: found.start()]

    return label, [entity for entity in SLICES if entity in named]


def _base(
    identity: str, name: str, entities: list[EntityName], trial: Any
) -> ConfigurationBranchModel | None:
    owner, slash, bare = name.partition("/")
    owners = [owner] if slash else [identity, settings.ARCHIVE_IDENTITY_NAME]
    rows = (
        ConfigurationBranchModel.objects.filter(
            name=bare if slash else name, owner__name__in=owners
        )
        .select_related("owner", "trail")
        .order_by("-timestamp", "-id")
    )
    matching = [
        row
        for row in rows
        if all(
            getattr(row.trail, f"{entity}_id") == getattr(trial, f"{entity}_id")
            for entity in SLICES
            if entity not in entities
        )
        and readable(row, identity)
    ]

    matching.sort(key=lambda row: row.owner.name != identity)

    return matching[0] if matching else None


def pinned(identity: str, asked: Mapping[str, str]) -> dict[EntityName, Any]:
    found: dict[EntityName, Any] = {}

    for entity in SLICES:
        value = asked.get(entity, "")

        if value == NONE and entity == "toolset":
            found[entity] = None
        elif value.isdigit():
            row = (
                entity_of(entity)
                .branch_model.objects.filter(pk=value)
                .select_related("owner", "trail")
                .first()
            )

            if row is not None and readable(row, identity):
                found[entity] = row

    return found


def shown(
    row: ConfigurationBranchModel, identity: str, pins: Mapping[EntityName, Any]
) -> Shown:
    row.trail = resolve_trail(row.trail)
    cell = Cell().using(row, row.name)

    for entity, variation in pins.items():
        variation_out = (
            None
            if variation is None
            else entity_of(entity).branch_out.model_validate(_resolved(variation))
        )
        cell = cell.set(entity, variation_out)

    held = {
        entity: NONE if pins[entity] is None else pins[entity].pk
        for entity in SLICES
        if entity in cell.variations
    }
    timeline = timeline_of(row)
    version = version_of(row, timeline)
    number = version.number
    latest = timeline[-1]

    return Shown(
        row=row,
        cell=cell,
        label=cell.label,
        owner=owner_of(row.owner.name, identity),
        fingerprint=short_fingerprint(cell.fingerprint),
        version=version,
        before=page_of(timeline[number - 2].pk, held) if number > 1 else None,
        after=page_of(timeline[number].pk, held) if number < len(timeline) else None,
        newer=None
        if version.latest
        else Newer(
            page_of(latest.pk, held),
            version_of(latest, timeline),
            _changes(row, latest, identity),
        ),
        slices=[_slice(entity, cell, row, held, pins, identity) for entity in SLICES],
        varies=page_of(row.pk) if held else None,
    )


def _resolved(row: Any) -> Any:
    row.trail = resolve_trail(row.trail)
    return row


def _slice(
    entity: EntityName,
    cell: Cell,
    row: ConfigurationBranchModel,
    held: Mapping[str, int | str],
    pins: Mapping[EntityName, Any],
    identity: str,
) -> Slice:
    trail = cell.variation(entity)
    own = getattr(cell.configuration.trail, entity) if cell.configuration else None
    fields = fields_of(entity, trail)

    if entity not in cell.variations:
        return Slice(
            entity,
            LABELS[entity],
            _named(entity, trail, identity),
            _short(trail),
            fields,
            page=page_of_variation(
                entity,
                branch_of(entity, trail, identity) if trail is not None else None,
                identity,
            ),
        )

    variation = pins[entity]
    version: Version | None = None
    newer: Newer | None = None

    if variation is not None:
        timeline = timeline_of(variation)
        version = version_of(variation, timeline)

        if not version.latest:
            latest = timeline[-1]
            newer = Newer(
                page_of(row.pk, {**held, entity: latest.pk}),
                version_of(latest, timeline),
                [],
            )

    return Slice(
        entity,
        LABELS[entity],
        NONE if variation is None else variation.name,
        _short(trail),
        fields,
        own=_named(entity, own, identity),
        changes=done(entity, own, trail),
        version=version,
        newer=newer,
        page=page_of_variation(entity, variation, identity),
    )


def _named(entity: EntityName, trail: Any, identity: str) -> str:
    if trail is None:
        return NONE

    row = branch_of(entity, trail, identity)
    return row.name if row is not None else short_fingerprint(trail.fingerprint)


def _short(trail: Any) -> str | None:
    return None if trail is None else short_fingerprint(trail.fingerprint)


def _changes(
    row: ConfigurationBranchModel, latest: ConfigurationBranchModel, identity: str
) -> list[Change]:
    latest.trail = resolve_trail(latest.trail)

    return [
        Change(
            LABELS[entity],
            name_of(entity, getattr(row.trail, entity), identity),
            name_of(entity, getattr(latest.trail, entity), identity),
        )
        for entity in SLICES
        if getattr(row.trail, f"{entity}_id") != getattr(latest.trail, f"{entity}_id")
    ]
