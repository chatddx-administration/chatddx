from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

from chatddx.bench.bench import Bench, NotReady, Ready, Trial
from chatddx.bench.cell import SLICES, Cell, Kept
from chatddx.repo.families.django import BranchModel
from chatddx.runtime.resolution import CellRefused


def crossed(cell: Cell, variations: Mapping[str, Sequence[Any]]) -> list[Cell]:
    axes = [
        [
            (entity, variation)
            for variation in sorted(
                variations[entity],
                key=lambda variation, entity=entity: not cell.holds(entity, variation),
            )
        ]
        for entity in SLICES
        if variations.get(entity)
    ]
    cells: dict[str, Cell] = {}

    for combination in product(*axes):
        varied = cell

        for entity, variation in combination:
            varied = varied.set(entity, variation)

        _ = cells.setdefault(varied.fingerprint, varied)

    return list(cells.values())


def reasons(error: NotReady | CellRefused) -> list[str]:
    match error:
        case CellRefused(refusals=refusals):
            return [
                f"{'not yet' if refusal.kind == 'later' else 'refused'}: "
                + f"{refusal.slice}: {refusal.reason}"
                for refusal in refusals
            ]
        case _:
            return [str(error)]


@dataclass(frozen=True)
class Planned:
    cell: Cell
    ready: Ready | None = None
    held_back: NotReady | CellRefused | None = None

    @property
    def why(self) -> list[str]:
        return [] if self.held_back is None else reasons(self.held_back)


@dataclass(frozen=True)
class Plan:
    cells: list[Planned]
    cases: list[BranchModel]
    tags: tuple[str, ...]
    seed: int | None

    @classmethod
    def of(
        cls,
        bench: Bench,
        cells: Iterable[Cell],
        tags: Iterable[str],
        seed: int | None,
    ) -> "Plan":
        tags = tuple(tags)
        planned: list[Planned] = []

        for cell in cells:
            try:
                planned.append(Planned(cell, ready=bench.ready(cell)))
            except (NotReady, CellRefused) as e:
                planned.append(Planned(cell, held_back=e))

        return cls(planned, bench.cases(tags), tags, seed)

    @property
    def ready(self) -> list[Ready]:
        return [planned.ready for planned in self.cells if planned.ready]

    @property
    def held_back(self) -> list[Planned]:
        return [planned for planned in self.cells if planned.held_back]

    def seed_of(self, ready: Ready) -> int | None:
        return None if ready.greedy else self.seed

    @property
    def kept(self) -> list[Kept]:
        return [ready.cell.kept(self.seed_of(ready)) for ready in self.ready]

    @property
    def trials(self) -> list[Trial]:
        return [
            Trial.on(ready, case, self.seed_of(ready))
            for ready in self.ready
            for case in self.cases
        ]

    @property
    def tagged(self) -> str:
        return " or ".join(self.tags)

    @property
    def description(self) -> str:
        many = "s" if len(self.cases) > 1 else ""
        cases = f"{len(self.cases)} case{many} tagged {self.tagged}"
        cells = [ready.cell for ready in self.ready] or [
            planned.cell for planned in self.cells
        ]

        if len(cells) == 1:
            [cell] = cells
            assert cell.stack

            return f"{cell.label} × {cell.stack.name} × {cases}"

        names = {cell.name for cell in cells}
        stacks = {cell.stack.name for cell in cells if cell.stack}

        if len(names) == 1 and len(stacks) == 1:
            return f"{len(cells)} cells of {names.pop()} × {stacks.pop()} × {cases}"

        return f"{len(cells)} cells × {cases}"
