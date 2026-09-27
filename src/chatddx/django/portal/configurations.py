# pyright: basic
"""
A configuration as its page shows it: a version of one, with whatever
variations were set in place of its own slices, as a run ran it or a
batch's cell runs it; each slice, what it asks and how; each variation
set, and what it does in place of the configuration's own; which of the
configuration's timeline it is, and what its latest changed; and where the
pages are, a run's the configuration as it ran.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _

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
    or_none,
    owner_of,
    readable,
    said,
    timeline_of,
    version_of,
)
from chatddx.history.models import RunModel
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.output.pydantic import VIEWS
from chatddx.repo.entity_names import EntityName
from chatddx.repo.names import short_fingerprint
from chatddx.repo.store.branch import AmbiguousBranchError, BranchNotFoundError
from chatddx.repo.utils import resolve_trail
from chatddx.worker.models import JobModel

# what the page calls each slice
LABELS: dict[str, Any] = {
    "instruction": _("Instruction"),
    "output": _("Output"),
    "coercion": _("Coercion"),
    "reasoning": _("Reasoning"),
    "sampling": _("Sampling"),
    "toolset": _("Toolset"),
}

# what the page calls each of a slice's fields, in the order it shows them
FIELDS: dict[str, dict[str, Any]] = {
    "instruction": {
        "system": _("System"),
        "user": _("User"),
        "variables": _("Variables"),
    },
    "output": {
        "guidance": _("Guidance"),
        "views": _("Views"),
        "answer_schema": _("Answer schema"),
    },
    "coercion": {
        "mode": _("Mode"),
        "schema_prompt": _("Schema prompt"),
        "tool_description": _("Tool description"),
    },
    "reasoning": {
        "effort": _("Effort"),
        "budget": _("Budget"),
    },
    "sampling": {
        "defaults": _("Defaults"),
        "temperature": _("Temperature"),
        "top_p": _("Top p"),
        "top_k": _("Top k"),
        "max_tokens": _("Max tokens"),
        "presence_penalty": _("Presence penalty"),
        "frequency_penalty": _("Frequency penalty"),
        "stop": _("Stop"),
    },
    "toolset": {
        "tools": _("Tools"),
        "guidance": _("Guidance"),
    },
}

# what a sampling's defaults are, in words
DEFAULTS: dict[str, Any] = {
    "recommended": _("what the LLM's facts recommend for the reasoning it comes to"),
    "generation_config": _("the LLM's generation config, as its server has it"),
}

# a change of a text too long for a line: its start, and that there is more
BRIEF = 60

# a cell's label: a variation set in it, from its end
_SET = re.compile(r"\+(" + "|".join(SLICES) + r")=([^+]*)$")


@dataclass(frozen=True)
class Slice:
    """A slice of the configuration, as the page shows it: its variation, set or its own."""

    entity: str
    label: Any
    name: str
    fingerprint: str | None
    fields: list[Field]
    # where it is set in place of the configuration's own: its own, and what
    # the one set does in its place
    own: str | None = None
    changes: list[Change] = field(default_factory=list[Change])
    # the version of the variation set, and its latest where it is an earlier
    version: Version | None = None
    newer: Newer | None = None

    @property
    def set(self) -> bool:
        return self.own is not None


@dataclass(frozen=True)
class Shown:
    """A version of a configuration, with any variations set in it, as its page shows it."""

    row: ConfigurationBranchModel
    cell: Cell
    # the cell's label: the configuration, and each variation set in it
    label: str
    owner: str
    # the fingerprint of the configuration the page comes to, set or not
    fingerprint: str
    version: Version
    before: str | None
    after: str | None
    newer: Newer | None
    slices: list[Slice]
    # the configuration's own page, its variations set aside, where any are set
    varies: str | None

    @property
    def set(self) -> list[Slice]:
        return [each for each in self.slices if each.set]


def page_of(row: int, pins: Mapping[str, int | str] | None = None) -> str:
    """
    The page of a version of a configuration, with each variation `pins`
    sets in it: a slice's version, or `none` for no toolset.
    """
    url = reverse("admin:portal_configuration_change", args=[row])
    pinned = pins or {}
    query = urlencode(
        [(entity, pinned[entity]) for entity in SLICES if entity in pinned]
    )

    return f"{url}?{query}" if query else url


def page_named(
    identity: str, configuration: str, set_names: Mapping[str, str] | None = None
) -> str | None:
    """
    The page of a configuration and what is set in it, by their names, as
    the identity has them now: what a batch's cell runs on.
    """
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
    """
    The page of the configuration as the run ran it: the version of the
    configuration its cell was put together from, and each variation set in
    it, as the run's trial holds them.
    """
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
        # no cell's configuration to be found: the configuration as it ran, where one holds it
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
    """A cell's label, as the configuration it names and the slices set in it."""
    named: list[str] = []

    while (found := _SET.search(label)) is not None:
        named.insert(0, found.group(1))
        label = label[: found.start()]

    return label, [entity for entity in SLICES if entity in named]


def _base(
    identity: str, name: str, entities: list[EntityName], trial: Any
) -> ConfigurationBranchModel | None:
    """
    The version of the configuration of the name the cell was put together
    from: the latest the identity reads whose slices, but for those set,
    are the trial's; its own first, as a name means it.
    """
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
    """
    The variations the page's address sets, each the version of one the
    identity reads, or None for no toolset; any other asked for aside.
    """
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
    """
    The configuration's version, gathered for its page, with each variation
    `pins` sets in place of its own.
    """
    row.trail = resolve_trail(row.trail)
    cell = Cell().using(row, row.name)

    for entity, variation in pins.items():
        variation_out = (
            None
            if variation is None
            else entity_of(entity).branch_out.model_validate(_resolved(variation))
        )
        cell = cell.set(entity, variation_out)

    # what is set in it, in the page's address: a variation equal to the
    # configuration's own is none of it
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
        # the configuration's other versions, with the same set in them
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
    fields = _fields(entity, trail)

    if entity not in cell.variations:
        return Slice(
            entity,
            LABELS[entity],
            _named(entity, trail, identity),
            _short(trail),
            fields,
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
        changes=_done(entity, own, trail),
        version=version,
        newer=newer,
    )


def _named(entity: EntityName, trail: Any, identity: str) -> str:
    if trail is None:
        return NONE

    row = branch_of(entity, trail, identity)
    return row.name if row is not None else short_fingerprint(trail.fingerprint)


def _short(trail: Any) -> str | None:
    return None if trail is None else short_fingerprint(trail.fingerprint)


def _values(entity: EntityName, trail: Any) -> dict[str, Any]:
    """A slice's fields, as the page compares them: a toolset's tools by name."""
    if trail is None:
        return {name: None for name in FIELDS[entity]}

    values = {name: getattr(trail, name, None) for name in FIELDS[entity]}

    if entity == "toolset":
        values["tools"] = [tool.name for tool in trail.tools]

    return values


def _done(entity: EntityName, own: Any, set_: Any) -> list[Change]:
    """What a variation set does in place of the configuration's own: each field it changes."""
    before, after = _values(entity, own), _values(entity, set_)

    if entity == "toolset" and (own is None or set_ is None):
        return [
            Change(
                FIELDS[entity]["tools"],
                _brief(before["tools"]) if own else gettext("none"),
                _brief(after["tools"]) if set_ else gettext("none"),
            )
        ]

    # a schema takes more than a line to say: that it changed
    return [
        Change(label)
        if name == "answer_schema" and before[name] and after[name]
        else Change(label, _brief(before[name]), _brief(after[name]))
        for name, label in FIELDS[entity].items()
        if before[name] != after[name]
    ]


def _brief(value: Any) -> str:
    """A value in a line: a text by its start, where it is longer than one."""
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return ", ".join(value) or gettext("none")

    if isinstance(value, dict) and "type" in value:
        return gettext("a schema")

    if isinstance(value, str):
        line = " ".join(value.split())

        if not line:
            return gettext("nothing")

        return (
            line
            if len(line) <= BRIEF and "\n" not in value.strip()
            else f"“{line[: BRIEF - 1]}…”"
        )

    return said(value)


def _changes(
    row: ConfigurationBranchModel, latest: ConfigurationBranchModel, identity: str
) -> list[Change]:
    """What the configuration's latest version holds in place of what `row` does."""
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


def _fields(entity: EntityName, trail: Any) -> list[Field]:
    labels = FIELDS[entity]

    match entity:
        case "instruction":
            return [
                Field(labels["system"], or_none(trail.system), text=True),
                Field(labels["user"], or_none(trail.user), text=True),
                Field(labels["variables"], items=list(trail.variables)),
            ]
        case "output":
            schema = trail.answer_schema

            return [
                Field(labels["guidance"], or_none(trail.guidance), text=True),
                Field(
                    labels["views"],
                    # in the order the outputs' views go, which the database doesn't keep
                    items=[
                        f"{view}: {trail.views[view]}"
                        for view in VIEWS
                        if view in trail.views
                    ],
                ),
                Field(
                    labels["answer_schema"],
                    gettext("none: the answer is free text")
                    if schema is None
                    else json.dumps(schema, indent=2, ensure_ascii=False),
                    folded=schema is not None,
                ),
            ]
        case "coercion":
            return [
                Field(labels["mode"], trail.mode),
                Field(labels["schema_prompt"], or_none(trail.schema_prompt), text=True),
                Field(
                    labels["tool_description"],
                    or_none(trail.tool_description),
                    text=True,
                ),
            ]
        case "reasoning":
            return [
                Field(labels["effort"], trail.effort),
                Field(
                    labels["budget"],
                    "—"
                    if trail.budget is None
                    else gettext("%(tokens)d thinking tokens")
                    % {"tokens": trail.budget},
                ),
            ]
        case "sampling":
            return [
                Field(
                    labels["defaults"], f"{trail.defaults}: {DEFAULTS[trail.defaults]}"
                ),
                *(
                    Field(label, said(getattr(trail, name)))
                    for name, label in labels.items()
                    if name != "defaults" and getattr(trail, name) is not None
                ),
            ]
        case _ if trail is None:
            return [Field(labels["tools"], gettext("none: no tool is offered"))]
        case _:
            return [
                Field(
                    labels["tools"],
                    items=[
                        f"{tool.name}: {tool.description}"
                        if tool.description
                        else tool.name
                        for tool in trail.tools
                    ],
                ),
                Field(labels["guidance"], or_none(trail.guidance), text=True),
            ]
