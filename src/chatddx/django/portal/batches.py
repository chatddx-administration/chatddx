# pyright: basic
"""
A plan as the portal keeps and shows it: what a batch stores of the plan it
was confirmed on, and the rows its pages show, the confirmation's and the
saved batch's alike.
"""

from dataclasses import dataclass
from typing import Any

from chatddx.bench.bench import Bench, HeldTo
from chatddx.bench.cell import SLICES
from chatddx.bench.plan import Plan
from chatddx.scoring.score import Scoring

# the most names a list on a page shows before it says how many more
SHOWN = 12


def cells_of(plan: Plan) -> list[dict[str, Any]]:
    """The cells a batch runs: what each sets, what it comes to, and its seed."""
    return [
        {
            "label": ready.cell.label,
            "set": ready.cell.set_names,
            "fingerprint": ready.cell.fingerprint,
            "seed": plan.seed_of(ready),
        }
        for ready in plan.ready
    ]


def held_back_of(plan: Plan) -> list[dict[str, Any]]:
    return [
        {
            "label": planned.cell.label,
            "set": planned.cell.set_names,
            "why": planned.why,
        }
        for planned in plan.held_back
    ]


def cases_of(plan: Plan) -> list[dict[str, str]]:
    return [
        {"name": case.name, "fingerprint": case.trail.fingerprint}
        for case in plan.cases
    ]


@dataclass(frozen=True)
class CellRow:
    label: str
    set: dict[str, str]
    seed: int | None
    # unseeded for greedy sampling, though the batch has a seed
    greedy: bool


@dataclass(frozen=True)
class HeldBackRow:
    label: str
    why: list[str]


@dataclass(frozen=True)
class Some:
    """Names, as many as a page shows, and how many more there are."""

    shown: list[str]
    more: int

    @classmethod
    def of(cls, names: list[str]) -> "Some":
        return cls(names[:SHOWN], max(len(names) - SHOWN, 0))


@dataclass(frozen=True)
class ScorerRow:
    """
    A scorer: how many of the cells offer what it reads, and, where any does,
    which of the cases it can hold them to.
    """

    name: str
    view: str
    target_kind: str | None
    offered: int
    have: int | None = None
    missing: Some | None = None
    unread: Some | None = None


@dataclass(frozen=True)
class Shown:
    """A batch's plan as its pages show it."""

    configuration: str
    cells: list[CellRow]
    held_back: list[HeldBackRow]
    cases: Some
    case_count: int
    seed: int | None

    @property
    def trials(self) -> int:
        return len(self.cells) * self.case_count

    @classmethod
    def of(
        cls,
        configuration: str,
        cells: list[dict[str, Any]],
        held_back: list[dict[str, Any]],
        cases: list[dict[str, Any]],
        seed: int | None,
    ) -> "Shown":
        return cls(
            configuration=configuration,
            cells=[
                CellRow(
                    cell["label"],
                    # in the slices' order, which the database doesn't keep
                    {
                        entity: cell["set"][entity]
                        for entity in SLICES
                        if entity in cell["set"]
                    },
                    cell["seed"],
                    cell["seed"] is None and seed is not None,
                )
                for cell in cells
            ],
            held_back=[HeldBackRow(cell["label"], cell["why"]) for cell in held_back],
            cases=Some.of([case["name"] for case in cases]),
            case_count=len(cases),
            seed=seed,
        )


def shown(plan: Plan) -> Shown:
    configuration = plan.cells[0].cell.name if plan.cells else ""

    return Shown.of(
        configuration, cells_of(plan), held_back_of(plan), cases_of(plan), plan.seed
    )


def scorers_of(bench: Bench, plan: Plan) -> list[ScorerRow]:
    """Each scorer, as `show` counts it, over the plan's cells and cases."""
    scoring = Scoring(bench.identity)
    offered = {scorer.name: 0 for scorer in scoring.scorers}
    held: dict[str, HeldTo] = {}
    outputs: set[str] = set()

    for ready in plan.ready:
        output = ready.cell.variation("output")

        for scorer in scoring.scorers:
            offered[scorer.name] += scorer.view in output.views

        # which cases a scorer can hold a cell to is the output's and the cases'
        if output.fingerprint in outputs:
            continue

        outputs.add(output.fingerprint)

        for row in bench.held_to(ready.cell, plan.cases, scoring):
            if row.offered:
                _ = held.setdefault(row.scorer.name, row)

    rows: list[ScorerRow] = []

    for scorer in scoring.scorers:
        row = held.get(scorer.name)
        rows.append(
            ScorerRow(
                name=scorer.name,
                view=scorer.view,
                target_kind=scorer.target_kind,
                offered=offered[scorer.name],
                have=None if row is None else row.have,
                missing=None if row is None else Some.of(row.missing),
                unread=None if row is None else Some.of(row.unread),
            )
        )

    return rows
