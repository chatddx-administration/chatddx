# pyright: basic
"""What the cell is, and how it resolves on its stack, before anything is sent."""

import json
from typing import Any, get_args

from pydantic import JsonValue
from rich.table import Table
from rich.text import Text

from chatddx.core.repl.cell import SLICES
from chatddx.core.repl.render import LABEL, LATER, REFUSED
from chatddx.core.repl.shell import Repl
from chatddx.repo.entities.coercion.pydantic import SLOT as SCHEMA_PROMPT
from chatddx.repo.entities.output.pydantic import VIEWS
from chatddx.repo.entities.reasoning.pydantic import Effort, ReasoningBranchOut
from chatddx.repo.entity_names import EntityName
from chatddx.repo.store.branch import select_visible_branch_models
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

EFFORTS: tuple[Effort, ...] = get_args(Effort.__value__)

type Parts = tuple[
    Reasoning | None, Sampling | None, Coercion | None, list[Tool], dict[str, str]
]


def show(repl: Repl) -> None:
    """
    Each slice's variation beside what it resolves to on the stack, whether
    or not the cell is refused, and the prompts it makes.
    """
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
