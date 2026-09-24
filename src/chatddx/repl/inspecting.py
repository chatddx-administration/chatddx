# pyright: basic
"""
What the cell is, and how it resolves on its stack, before anything is sent;
and what any branch is, and what came of the runs that used it.
"""

import json
from typing import Any, cast, get_args

from django.db.models import Q
from pydantic import BaseModel, JsonValue
from rich.table import Table
from rich.text import Text

from chatddx.history.models import RunModel, RunStatus
from chatddx.repl.cell import SLICES
from chatddx.repl.render import LABEL, LATER, REFUSED
from chatddx.repl.scoring import summary
from chatddx.repl.shell import Repl
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.case.pydantic import TARGET_KINDS
from chatddx.repo.entities.coercion.pydantic import SLOT as SCHEMA_PROMPT
from chatddx.repo.entities.output.pydantic import VIEWS
from chatddx.repo.entities.reasoning.pydantic import Effort, ReasoningBranchOut
from chatddx.repo.entity_names import ENTITY_NAMES, EntityName
from chatddx.repo.families.pydantic import TrailOut
from chatddx.repo.names import short_fingerprint
from chatddx.repo.store.branch import (
    get_visible_branch_model,
    select_visible_branch_models,
)
from chatddx.runtime.resolution import (
    CellRefused,
    Coercion,
    Reasoning,
    Resolution,
    Sampling,
    SliceRefusal,
    Slices,
    Tool,
    realize,
)
from chatddx.runtime.run import FINAL_RESULT
from chatddx.scoring.score import Scoring

EFFORTS: tuple[Effort, ...] = get_args(Effort.__value__)

type Parts = tuple[
    Reasoning | None, Sampling | None, Coercion | None, list[Tool], dict[str, str]
]


# Where a run's trial holds each entity's trail, among those one path reaches
HELD_AT: dict[str, str] = {
    "case": "trial__case",
    "configuration": "trial__configuration",
    "stack": "trial__stack",
    "client": "client",
    "machine": "trial__stack__machine",
    "llm": "trial__stack__llm",
    "serving": "trial__stack__serving",
    **{entity: f"trial__configuration__{entity}" for entity in SLICES},
}

STACK_PARTS: tuple[EntityName, ...] = ("machine", "os", "llm", "serving")


def show(repl: Repl, entity: str | None = None, name: str | None = None) -> None:
    """
    The cell: each slice's variation beside what it resolves to on the stack,
    whether or not the cell is refused, and the prompts it makes. Or ENTITY's
    NAME, or the cell's ENTITY: what it is, and what came of your runs with
    it.
    """
    if entity is None:
        _show_cell(repl)
    elif entity not in ENTITY_NAMES:
        repl.error(f"no entity '{entity}': {', '.join(ENTITY_NAMES)}")
    else:
        _show_branch(repl, cast(EntityName, entity), name)


def _show_cell(repl: Repl) -> None:
    cell = repl.cell

    if not (cell.configuration or cell.stack):
        repl.error("the cell is empty: use CONFIGURATION, on STACK")
        return

    repl.say_cell()

    refusals: list[SliceRefusal] = []
    resolution: Resolution | None = None
    parts: Parts | None = None

    if cell.configuration and cell.stack:
        try:
            resolution = repl.resolve()
            parts = (
                resolution.reasoning,
                resolution.sampling,
                resolution.coercion,
                resolution.tools,
                resolution.slots,
            )
        except CellRefused as e:
            refusals = e.refusals
            parts = (e.reasoning, e.sampling, e.coercion, e.tools, e.slots)

    table = Table(box=None, header_style="bold")
    table.add_column("slice")
    table.add_column("variation")
    table.add_column("on the stack" if cell.stack else "")

    if cell.stack:
        llm = repl.name_of("llm", cell.stack.trail.llm)
        details = cell.stack.details
        where = f"{llm}, served as {details.served_name} at {details.endpoint}"
        table.add_row("stack", cell.stack.name, _outcome("stack", refusals, where))

    if cell.configuration:
        slices = cell.slices

        for entity in SLICES:
            realized = _realized(entity, slices, parts) if parts else ""
            table.add_row(
                entity,
                _variation(repl, entity),
                _outcome(entity, refusals, realized),
            )

    repl.console.print(table)

    if resolution:
        system, user = resolution.render("‹case›")
        repl.console.print("system", style="bold")
        repl.console.print(Text(_clipped(system) or "(none)"))
        repl.console.print("user", style="bold")
        repl.console.print(Text(user))


def _show_branch(repl: Repl, entity: EntityName, name: str | None) -> None:
    found = _named(repl, entity, name) if name is not None else _in_cell(repl, entity)

    if found is None:
        return

    branch: Any = entity_of(entity).branch_out.model_validate(found)
    header = Text(f"{entity} {branch.name}", style="bold")

    if branch.owner.name != repl.identity:
        header.append(f", {branch.owner.name}'s")

    header.append(f"  {short_fingerprint(branch.trail.fingerprint)}", style=LABEL)
    repl.console.print(header)

    table = Table(box=None, show_header=False)
    table.add_column(style=LABEL)
    table.add_column()
    content = type(branch.trail).model_fields

    for field in content:
        if field not in TrailOut.model_fields:
            _add_rows(repl, table, field, getattr(branch.trail, field))

    for field in type(branch.details).model_fields:
        _add_rows(repl, table, field, getattr(branch.details, field))

    _add_rows(repl, table, "tags", " ".join(branch.tags))
    repl.console.print(table)
    _show_runs(repl, entity, branch.trail.id)


def _named(repl: Repl, entity: EntityName, name: str) -> Any:
    if entity == "configuration":
        return repl.configuration_named(name)

    return get_visible_branch_model(entity, repl.identity, name)


def _in_cell(repl: Repl, entity: EntityName) -> Any:
    """The branch of `entity` the cell holds, or None where it holds none."""
    cell = repl.cell
    trail: Any = None

    if entity == "configuration":
        trail = cell.configuration
    elif entity == "stack":
        trail = cell.stack
    elif entity in SLICES and cell.configuration:
        if entity in cell.variations:
            if cell.variations[entity] is None:
                repl.error(f"the cell has no {entity}")
            return cell.variations[entity]

        trail = getattr(cell.configuration.trail, entity)
    elif entity in STACK_PARTS and cell.stack:
        trail = getattr(cell.stack.trail, entity)
    elif entity in (*SLICES, *STACK_PARTS):
        where = "configuration" if entity in SLICES else "stack"
        repl.error(f"the cell has no {where}: show {entity} NAME")
        return None
    else:
        repl.error(f"a {entity} isn't in the cell: show {entity} NAME")
        return None

    if trail is None:
        repl.error(f"the cell has no {entity}")
        return None

    if entity in ("configuration", "stack"):
        return trail

    return get_visible_branch_model(entity, repl.identity, trail=trail.id)


def _add_rows(repl: Repl, table: Table, field: str, value: Any) -> None:
    """A field as rows: a flat mapping a row per key, anything else one."""
    if isinstance(value, BaseModel) and not isinstance(value, TrailOut):
        value = value.model_dump(mode="json", exclude_none=True)

    if (
        isinstance(value, dict)
        and value
        and all(not isinstance(item, (dict, list)) for item in value.values())
    ):
        # jsonb keeps no order: a vocabulary's keys go in its own
        for vocabulary in (TARGET_KINDS, VIEWS):
            if set(value) <= set(vocabulary):
                value = {key: value[key] for key in vocabulary if key in value}

        for key, item in value.items():
            table.add_row(f"{field}.{key}", _text(repl, item))
        return

    table.add_row(field, _text(repl, value))


def _text(repl: Repl, value: Any) -> Text:
    if value is None or (isinstance(value, (str, list, dict)) and not value):
        return Text("—", style=LABEL)

    match value:
        case TrailOut():
            return Text(repl.name_of(entity_of(value).name, value))
        case [TrailOut(), *_]:
            return Text(
                " ".join(repl.name_of(entity_of(item).name, item) for item in value)
            )
        case str():
            return Text(value)
        case list() if all(isinstance(item, (str, int, float)) for item in value):
            return Text(" ".join(str(item) for item in value))
        case dict() | list():
            return Text(json.dumps(value, indent=2, ensure_ascii=False))
        case _:
            return Text(json.dumps(value) if isinstance(value, bool) else str(value))


def _show_runs(repl: Repl, entity: EntityName, trail: int) -> None:
    """Your runs with the trail, and each scorer's latest scores of them."""
    match entity:
        case "os":
            with_it = Q(trial__stack__os=trail) | Q(trial__stack__host_os=trail)
        case "tool":
            with_it = Q(trial__configuration__toolset__tools__contains=[trail])
        case "scorer":
            with_it = Q(scores__scorer=trail, scores__owner__name=repl.identity)
        case _:
            with_it = Q(**{HELD_AT[entity]: trail})

    runs = list(
        RunModel.objects.filter(with_it, owner__name=repl.identity)
        .distinct()
        .prefetch_related("scores")
    )

    if not runs:
        repl.console.print(f"no runs of yours with this {entity}", style=LABEL)
        return

    errored = sum(run.status == RunStatus.ERRORED for run in runs)
    said = f"{len(runs)} run{'s' if len(runs) > 1 else ''} of yours with it"
    repl.console.print(said + (f", {errored} errored" if errored else ""), style=LABEL)

    scoring = Scoring(repl.identity)
    made = [score for run in runs for score in scoring.latest(run)]

    if entity == "scorer":
        made = [score for score in made if score.scorer_id == trail]

    if made:
        summary(repl, scoring, made)


def reasoning(repl: Repl) -> None:
    """
    What each reasoning variation does on each stack, with the sampling the
    cell's configuration pulls in. Stacks every variation resolves alike on
    share a column: they differ in nothing the table shows.
    """
    cell = repl.cell
    variations = sorted(
        (
            ReasoningBranchOut.model_validate(model)
            for model in select_visible_branch_models("reasoning", repl.identity)
        ),
        key=lambda v: (
            EFFORTS.index(v.trail.effort),
            v.trail.budget or 0,
            v.name,
        ),
    )
    slices = cell.slices if cell.configuration else None

    caption = (
        f"sampling as '{repl.name_of('sampling', slices.sampling)}' pulls it in"
        if slices
        else "the cell has no configuration: no sampling is pulled in"
    )
    columns: dict[tuple[str, ...], tuple[list[str], list[Text]]] = {}

    for stack in repl.stacks():
        efforts = [
            _effort(
                *realize(
                    variation.trail,
                    slices.sampling if slices else None,
                    repl.facts_of(stack),
                    stack.trail.serving,
                )
            )
            for variation in variations
        ]
        names, _ = columns.setdefault(
            tuple(effort.plain for effort in efforts), ([], efforts)
        )
        current = cell.stack is not None and cell.stack.name == stack.name
        names.append(f"▸ {stack.name}" if current else stack.name)

    table = Table(header_style="bold", show_lines=True, caption=caption)
    table.add_column("reasoning")

    for names, _ in columns.values():
        table.add_column("\n".join(names), overflow="fold")

    for i, variation in enumerate(variations):
        current = slices is not None and _same(slices.reasoning, variation.trail)
        table.add_row(
            f"▸ {variation.name}" if current else variation.name,
            *(efforts[i] for _, efforts in columns.values()),
        )

    repl.console.print(table)


def _variation(repl: Repl, entity: EntityName) -> Text:
    cell = repl.cell
    assert cell.configuration

    own = repl.name_of(entity, getattr(cell.configuration.trail, entity))

    if entity not in cell.variations:
        return Text(own)

    text = Text(cell.set_name(entity), style="bold")
    text.append(f" (set; {cell.name} has {own})", style=LABEL)
    return text


def _outcome(entity: str, refusals: list[SliceRefusal], realized: str) -> Text:
    mine = [r for r in refusals if r.slice == entity]

    if not mine:
        return Text(realized)

    text = Text()

    for i, refusal in enumerate(mine):
        if i:
            text.append("\n")
        if refusal.kind == "later":
            text.append(f"not yet: {refusal.reason}", style=LATER)
        else:
            text.append(f"refused: {refusal.reason}", style=REFUSED)

    return text


def _realized(entity: str, slices: Slices, parts: Parts) -> str:
    reasoning, sampling, coercion, tools, slots = parts
    free_text = slices.output.json_schema is None
    views = ", ".join(v for v in VIEWS if v in slices.output.views) or "none"

    match entity:
        case "reasoning" if reasoning:
            writes = _writes(reasoning.writes)
            if reasoning.effort == "default":
                return f"the LLM's default, '{reasoning.intent}': {writes}"
            if reasoning.effort != reasoning.intent:
                return f"collapses into '{reasoning.intent}': {writes}"
            return writes
        case "sampling" if sampling:
            return f"{sampling.source}: {_writes(sampling.writes) or 'nothing'}"
        case "output":
            return f"{'free text' if free_text else 'a schema'}; views: {views}"
        case "coercion" if free_text:
            return "nothing to coerce in free text"
        case "coercion" if coercion:
            return _coerced(coercion, SCHEMA_PROMPT in slots)
        case "instruction":
            return f"filled: {', '.join(slots) or 'no slots'}"
        case "toolset" if tools:
            return f"offered: {', '.join(tool.name for tool in tools)}"
        case _:
            return ""


def _coerced(coercion: Coercion, shown: bool) -> str:
    """How the answer is held to its schema, and how the LLM reads it."""
    match coercion.mode:
        case "native":
            held = "response_format: guided decoding holds the answer to the schema"
        case "tool":
            held = f"a {FINAL_RESULT} tool holds the answer to the schema"
        case "prompted":
            held = "nothing holds the answer to the schema"

    reads = [
        *(["as the tool's parameters"] if coercion.mode == "tool" else []),
        *(["through schema_prompt"] if shown else []),
    ]
    how = (
        f"the LLM reads it {' and '.join(reads)}"
        if reads
        else "the LLM doesn't read it"
    )
    auto = f"auto → {coercion.mode}: " if coercion.requested == "auto" else ""
    note = f"\n{coercion.note}" if coercion.note else ""

    return f"{auto}{held}; {how}{note}"


def _effort(
    reasoning: Reasoning | None,
    sampling: Sampling | None,
    refusals: list[SliceRefusal],
) -> Text:
    """
    A reasoning variation on a stack, as the table shows it: the intent it
    ends at, where that isn't its effort (the LLM's default, or a
    collapse), and what it and the sampling write.
    """
    if refusals:
        return Text(
            "\n".join(f"refused: {refusal.reason}" for refusal in refusals),
            style=REFUSED,
        )

    assert reasoning

    text = Text()

    if reasoning.effort != reasoning.intent:
        text.append(f"→ {reasoning.intent}\n")

    text.append(_writes(reasoning.writes) or "nothing")

    if sampling:
        text.append(f"\n{_writes(sampling.writes) or 'nothing'}", style=LABEL)

    return text


def _same(trail: Any, other: Any) -> bool:
    return trail.fingerprint == other.fingerprint


def _writes(writes: dict[str, JsonValue], prefix: str = "") -> str:
    """Request fields as `path=value`, a nested field by its dotted path."""
    fields: list[str] = []

    for key, value in writes.items():
        if isinstance(value, dict):
            fields.append(_writes(value, f"{prefix}{key}."))
        else:
            fields.append(f"{prefix}{key}={json.dumps(value)}")

    return " ".join(field for field in fields if field)


def _clipped(text: str, lines: int = 30) -> str:
    kept = text.splitlines()

    if len(kept) <= lines:
        return text

    return "\n".join(kept[:lines]) + f"\n… {len(kept) - lines} more lines"
