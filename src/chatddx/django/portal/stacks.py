# pyright: basic
"""
A stack as its page shows it: the version asked for, which of its timeline
it is, and what the latest changed of it; what it is, part by part, the
LLM, the serving, the machine and its system, each as the version the
stack reads has it, the LLM as a run read it where the page is a run's; and
where the pages are, a run's the version it read.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.db.models import Model
from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _, ngettext
from pydantic import JsonValue

from chatddx.bench.bench import Bench
from chatddx.core import settings
from chatddx.history.models import RunModel
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.llm.django import LLMBranchModel
from chatddx.repo.entities.llm.pydantic import (
    CoercionFacts,
    LLMBranchOut,
    LLMDetails,
    LLMSpecs,
    ModeFact,
    ReasoningFacts,
    Refusal,
    SamplingFacts,
)
from chatddx.repo.entities.machine.pydantic import MachineDetails
from chatddx.repo.entities.os.pydantic import OsDetails
from chatddx.repo.entities.reasoning.pydantic import INTENTS
from chatddx.repo.entities.serving.pydantic import ServingDetails, ServingTrailBase
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.entities.stack.pydantic import StackBranchOut, StackDetails
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.names import short_fingerprint
from chatddx.repo.store.branch import (
    AmbiguousBranchError,
    BranchNotFoundError,
    get_visible_branch_model,
)
from chatddx.repo.utils import resolve_trail

# the stack's parts, as its trail holds them: the field, and the kind of each
PARTS: tuple[tuple[str, EntityName], ...] = (
    ("llm", "llm"),
    ("serving", "serving"),
    ("machine", "machine"),
    ("os", "os"),
    ("host_os", "os"),
)

# what the page calls each part
LABELS: dict[str, Any] = {
    "llm": _("LLM"),
    "serving": _("Serving"),
    "machine": _("Machine"),
    "os": _("System"),
    "host_os": _("Host system"),
}

# what describes each kind of part, where the identity has no branch of it
BLANK: dict[str, Any] = {
    "llm": LLMDetails,
    "serving": ServingDetails,
    "machine": MachineDetails,
    "os": OsDetails,
}

# what the page calls each of an LLM's details, where a later version changed it
LLM_DETAILS: dict[str, Any] = {
    "source": _("Source"),
    "specs": _("Specs"),
    "facts": _("Facts"),
}

# what the page calls each of the stack's details, in the order it shows them
DETAILS: dict[str, Any] = {
    "endpoint": _("Endpoint"),
    "served_name": _("Served name"),
    "api": _("API"),
    "credential": _("Credential"),
    "max_jobs": _("Slots"),
}


@dataclass(frozen=True)
class Field:
    """A line of what a record holds: what it is, and its value, or its items."""

    label: Any
    value: str = "—"
    items: list[str] = field(default_factory=list[str])
    # shown as code: a path, a name as it is sent
    code: bool = False
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
    What the latest version holds in place of what this one does, or, of
    what takes more than a line to say, that it changed.
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


@dataclass(frozen=True)
class Part:
    """A part of the stack, as the version the stack reads has it."""

    key: str
    label: Any
    name: str
    fingerprint: str
    fields: list[Field]
    # which of its timeline it is, where the page shows a version of it asked for
    version: Version | None = None
    newer: Newer | None = None


@dataclass(frozen=True)
class Shown:
    """The stack's version, as its page shows it."""

    row: StackBranchModel
    stack: StackBranchOut
    owner: str
    fingerprint: str
    version: Version
    before: str | None
    after: str | None
    newer: Newer | None
    details: list[Field]
    parts: list[Part]
    # the LLM the page shows, whose facts the Test sends by
    llm: LLMBranchOut | None
    # what the page's address asks of it beside the version: its LLM's
    query: str


def page_of(row: int, llm: int | None = None) -> str:
    """The page of a version of a stack, with the version of its LLM where given."""
    url = reverse("admin:portal_stack_change", args=[row])
    return f"{url}?llm={llm}" if llm else url


def page_of_run(run: RunModel) -> str | None:
    """The page of the stack as a run read it: the stack's version, and its LLM's."""
    if run.stack_branch_id is None:
        return None

    return page_of(run.stack_branch_id, run.llm_branch_id)


def page_named(identity: str, name: str) -> str | None:
    """The page of the stack of the name as the identity has it now: its latest."""
    try:
        row = get_visible_branch_model("stack", identity, name)
    except (BranchNotFoundError, AmbiguousBranchError):
        return None

    return page_of(row.pk)


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


def shown(row: StackBranchModel, identity: str, llm: int | None = None) -> Shown:
    """
    The stack's version, gathered for its page; its LLM the version `llm`
    where that is one the identity reads of the LLM the stack holds.
    """
    row.trail = resolve_trail(row.trail)
    stack = StackBranchOut.model_validate(row)
    bench = Bench(identity)
    timeline = timeline_of(row)
    version = version_of(row, timeline)
    number = version.number
    latest = timeline[-1]
    pinned = _pinned(llm, stack, identity)

    # the stack's other versions are as they are now, their LLM's latest too:
    # the LLM a run read goes with the version it read alone
    return Shown(
        row=row,
        stack=stack,
        owner=_owner(row.owner.name, identity),
        fingerprint=short_fingerprint(row.trail.fingerprint),
        version=version,
        before=page_of(timeline[number - 2].pk) if number > 1 else None,
        after=page_of(timeline[number].pk) if number < len(timeline) else None,
        newer=None
        if version.latest
        else Newer(
            page_of(latest.pk),
            version_of(latest, timeline),
            _changes(row, latest, identity),
        ),
        details=_details(stack, bench),
        parts=[
            _part(key, entity, getattr(stack.trail, key), identity, pinned, row)
            for key, entity in PARTS
            if getattr(stack.trail, key) is not None
        ],
        llm=_llm_out(pinned, stack, identity),
        query=f"?llm={pinned.pk}" if pinned is not None else "",
    )


def _pinned(llm: int | None, stack: StackBranchOut, identity: str) -> Any:
    """The LLM's version asked for, where it is one of the stack's LLM's to read."""
    if llm is None:
        return None

    found = (
        LLMBranchModel.objects.filter(pk=llm, trail_id=stack.trail.llm.id)
        .select_related("owner", "trail")
        .first()
    )

    return found if found is not None and readable(found, identity) else None


def _branch_of(entity: EntityName, trail: Any, identity: str) -> Any:
    """The newest version of the identity's branch of the part, if it has one."""
    try:
        return get_visible_branch_model(entity, identity, trail=trail.id)
    except (BranchNotFoundError, AmbiguousBranchError):
        return None


def _llm_out(pinned: Any, stack: StackBranchOut, identity: str) -> LLMBranchOut | None:
    row = pinned or _branch_of("llm", stack.trail.llm, identity)
    return None if row is None else LLMBranchOut.model_validate(row)


def _part(
    key: str,
    entity: EntityName,
    trail: Any,
    identity: str,
    pinned: Any,
    stack_row: StackBranchModel,
) -> Part:
    row = (pinned if key == "llm" else None) or _branch_of(entity, trail, identity)
    details: Any = (
        entity_of(entity).branch_out.model_validate(row).details
        if row is not None
        else BLANK[entity]()
    )
    version: Version | None = None
    newer: Newer | None = None

    if key == "llm" and pinned is not None:
        timeline = timeline_of(pinned)
        version = version_of(pinned, timeline)

        if not version.latest:
            latest = timeline[-1]
            newer = Newer(
                page_of(stack_row.pk),
                version_of(latest, timeline),
                [
                    Change(label)
                    for name, label in LLM_DETAILS.items()
                    if pinned.details.get(name) != latest.details.get(name)
                ],
            )

    match key:
        case "llm":
            fields = _llm_fields(trail, details)
        case "serving":
            fields = _serving_fields(trail, details)
        case "machine":
            fields = _machine_fields(trail, details)
        case _:
            fields = _os_fields(trail, details)

    return Part(
        key,
        LABELS[key],
        row.name if row is not None else short_fingerprint(trail.fingerprint),
        short_fingerprint(trail.fingerprint),
        fields,
        version,
        newer,
    )


def _details(stack: StackBranchOut, bench: Bench) -> list[Field]:
    details = stack.details
    credential = details.credential
    held = bench.secret(credential) is not None if credential else None

    return [
        Field(DETAILS["endpoint"], _or_none(details.endpoint), code=True),
        Field(DETAILS["served_name"], _or_none(details.served_name), code=True),
        Field(DETAILS["api"], _or_none(details.api)),
        Field(
            DETAILS["credential"],
            gettext("none: it takes no secret")
            if credential is None
            else gettext("%(name)s, a secret of yours") % {"name": credential}
            if held
            else gettext("%(name)s, a secret you don't have") % {"name": credential},
            trouble=held is False,
        ),
        Field(
            DETAILS["max_jobs"],
            ngettext(
                "%(jobs)d of the worker's jobs at once",
                "%(jobs)d of the worker's jobs at once",
                details.max_jobs,
            )
            % {"jobs": details.max_jobs},
        ),
        Field(_("Tags"), " ".join(stack.tags) or "—"),
    ]


def _changes(
    row: StackBranchModel, latest: StackBranchModel, identity: str
) -> list[Change]:
    """What the latest version holds in place of what `row` does."""
    # each detail as it stands, one left out as its default: slots are 1
    was, now = (
        StackDetails.model_validate(each.details).model_dump(mode="json")
        for each in (row, latest)
    )
    changes = [
        Change(label, _said(was[key]), _said(now[key]))
        for key, label in DETAILS.items()
        if was[key] != now[key]
    ]
    latest.trail = resolve_trail(latest.trail)

    for key, entity in PARTS:
        before, after = getattr(row.trail, key), getattr(latest.trail, key)

        if getattr(before, "id", None) != getattr(after, "id", None):
            changes.append(
                Change(
                    LABELS[key],
                    _name_of(entity, before, identity),
                    _name_of(entity, after, identity),
                )
            )

    return changes


def _name_of(entity: EntityName, trail: Any, identity: str) -> str:
    if trail is None:
        return "—"

    row = _branch_of(entity, trail, identity)
    short = short_fingerprint(trail.fingerprint)

    return f"{row.name} ({short})" if row is not None else short


def _llm_fields(trail: Any, details: LLMDetails) -> list[Field]:
    specs = details.specs or LLMSpecs()
    facts = details.facts

    return [
        Field(_("Snapshot"), trail.snapshot, code=True),
        Field(_("Source"), _or_none(details.source), code=details.source is not None),
        Field(_("Family"), _or_none(specs.family)),
        Field(_("Parameters"), _parameters(specs)),
        Field(_("Quantization"), _or_none(specs.quantization)),
        Field(_("Context"), _tokens(specs.context_length)),
        Field(_("Licence"), _or_none(specs.licence)),
        Field(_("Reasoning"), items=_reasoning(facts.reasoning)),
        Field(_("Sampling"), items=_sampling(facts.sampling)),
        Field(_("Coercion"), items=_coercion(facts.coercion)),
        Field(
            _("Profile"),
            items=[f"{name} = {_said(value)}" for name, value in facts.profile.items()],
        ),
    ]


def _serving_fields(trail: ServingTrailBase, details: ServingDetails) -> list[Field]:
    provided = trail.provides()
    parsers = [
        gettext("a reasoning parser") if "reasoning_parser" in provided else None,
        gettext("a tool-call parser") if "tool_call_parser" in provided else None,
    ]

    return [
        Field(_("Engine"), trail.engine, code=True),
        Field(_("Arguments"), items=_arguments(trail.args)),
        Field(_("Environment"), items=[f"{k}={v}" for k, v in trail.env.items()]),
        Field(_("Performance"), items=_arguments(details.performance)),
        Field(
            _("Provides"),
            gettext(" and ").join(parser for parser in parsers if parser)
            or gettext(
                "no parser: the thinking stays in the text, and no tool is called"
            ),
        ),
    ]


def _machine_fields(trail: Any, details: MachineDetails) -> list[Field]:
    specs = details.specs

    return [
        Field(_("Machine id"), str(trail.machine_id), code=True),
        Field(
            _("GPUs"),
            items=[
                f"{gpu.model}, {gpu.memory_mib} MiB ({gpu.uuid})"
                for gpu in (specs.gpus if specs else [])
            ],
        ),
        Field(_("CPU"), _or_none(specs.cpu if specs else None)),
        Field(_("RAM"), f"{specs.ram_gib} GiB" if specs and specs.ram_gib else "—"),
        Field(_("Location"), _or_none(specs.location if specs else None)),
        Field(
            _("Unreliable"),
            gettext(
                "yes: a cloud provider's, nothing below the requests can be checked"
            )
            if details.unreliable
            else gettext("no"),
        ),
    ]


def _os_fields(trail: Any, details: OsDetails) -> list[Field]:
    specs = details.specs

    return [
        Field(_("Toplevel"), trail.toplevel, code=True),
        Field(
            _("Flake revision"),
            _or_none(details.flake_rev),
            code=bool(details.flake_rev),
        ),
        Field(_("Hostname"), _or_none(specs.hostname if specs else None)),
        Field(_("Kernel"), _or_none(specs.kernel if specs else None)),
        Field(_("NVIDIA driver"), _or_none(specs.nvidia_driver if specs else None)),
        Field(
            _("Nixpkgs revision"),
            _or_none(specs.nixpkgs_rev if specs else None),
            code=bool(specs and specs.nixpkgs_rev),
        ),
    ]


def _reasoning(facts: ReasoningFacts) -> list[str]:
    said = (
        [gettext("by default: %(intent)s") % {"intent": facts.default}]
        if facts.default
        else []
    )

    for intent in INTENTS:
        fact = getattr(facts, intent)

        if fact is not None:
            said.append(f"{intent}: {_fact(fact)}")

    if facts.budget is not None:
        budget = facts.budget
        said.append(
            gettext("a budget: %(fact)s")
            % {
                "fact": _fact(budget)
                if isinstance(budget, Refusal)
                else _needing(budget.field, budget.needs)
            }
        )

    return said


def _sampling(facts: SamplingFacts) -> list[str]:
    said = [
        gettext("recommended for %(intent)s: %(values)s")
        % {"intent": intent, "values": _said(values.model_dump(exclude_none=True))}
        for intent, values in facts.recommended.items()
    ]

    if facts.generation_config is not None:
        written = facts.generation_config.model_dump(exclude_none=True)
        said.append(
            gettext("its generation config: %(values)s")
            % {"values": _said(written) if written else gettext("sets nothing")}
        )

    return said


def _coercion(facts: CoercionFacts) -> list[str]:
    said = (
        [gettext("auto: %(mode)s") % {"mode": facts.default}] if facts.default else []
    )

    for mode in ("native", "tool", "prompted"):
        fact = getattr(facts, mode)

        match fact:
            case None:
                continue
            case Refusal():
                said.append(f"{mode}: {_fact(fact)}")
            case ModeFact(needs=needs, note=note):
                said.append(
                    f"{mode}: {_needing(None, needs)}" + (f"; {note}" if note else "")
                )

    return said


def _fact(fact: Any) -> str:
    match fact:
        case str():
            return gettext("as %(intent)s") % {"intent": fact}
        case Refusal(refused=why):
            return gettext("refused: %(why)s") % {"why": why}
        case _:
            return _said(fact)


def _needing(field_name: str | None, needs: Sequence[str]) -> str:
    wanted = gettext(" and ").join(
        gettext("a reasoning parser")
        if need == "reasoning_parser"
        else gettext("a tool-call parser")
        for need in needs
    )
    said = field_name or ""

    if wanted:
        return (f"{said}, " if said else "") + gettext("needs %(what)s") % {
            "what": wanted
        }

    return said or gettext("needs nothing")


def _arguments(args: dict[str, JsonValue]) -> list[str]:
    return [
        name if value is True else f"{name} = {_said(value)}"
        for name, value in args.items()
    ]


def _parameters(specs: LLMSpecs) -> str:
    if specs.parameters_b is None:
        return "—"

    whole = gettext("%(billions)s B") % {"billions": f"{specs.parameters_b:g}"}

    if specs.active_parameters_b is None:
        return whole

    return gettext("%(whole)s, %(active)s B active") % {
        "whole": whole,
        "active": f"{specs.active_parameters_b:g}",
    }


def _tokens(count: int | None) -> str:
    if count is None:
        return "—"

    return ngettext("%(count)d token", "%(count)d tokens", count) % {"count": count}


def _owner(owner: str, identity: str) -> str:
    if owner == identity:
        return gettext("yours")

    if owner == settings.ARCHIVE_IDENTITY_NAME:
        return gettext("the archive's")

    return gettext("%(owner)s's") % {"owner": owner}


def _or_none(value: Any) -> str:
    return "—" if value is None or value == "" else str(value)


def _said(value: Any) -> str:
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
            return "{" + _said(value) + "}"
        case list():
            return "[" + _said(value) + "]"
        case _:
            return _said(value)
