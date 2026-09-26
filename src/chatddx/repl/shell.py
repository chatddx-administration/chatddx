from collections.abc import Iterable
from typing import Any, override

from rich.console import Console
from rich.text import Text

from chatddx.history.models import RunModel
from chatddx.repl.bench import Bench, drawn_seed
from chatddx.repl.render import LATER, REFUSED
from chatddx.repo.entity_names import ENTITY_NAMES
from chatddx.runtime.resolution import SliceRefusal
from chatddx.scoring.score import Scoring

DRAWN: Any = object()


class Repl(Bench):
    def __init__(
        self,
        identity_name: str,
        console: Console,
        transport: Any = None,
        seed: int | None = DRAWN,
    ):
        super().__init__(identity_name, transport)
        self.console: Console = console
        self.seed: int | None = drawn_seed() if seed is DRAWN else seed

        self._completions: dict[str, list[str]] | None = None

    @property
    def prompt(self) -> str:
        cell = self.cell
        stack = f"×{cell.stack.name}" if cell.stack else ""
        held = f" {cell.label}{stack}" if cell.configuration or cell.stack else ""
        seed = f"#{self.seed}" if self.seed is not None else "#none"
        return f"{self.identity}{held} {seed}> "

    def completions(self) -> dict[str, list[str]]:
        if self._completions is None:
            self._completions = {
                entity: self.names(entity) for entity in ENTITY_NAMES
            } | {"batch:tag": self.tags("case"), "seed:seed": ["none"]}

        latest = RunModel.objects.filter(owner__name=self.identity).order_by(
            "-timestamp", "-pk"
        )
        outstanding = Scoring(self.identity).outstanding_runs()

        return self._completions | {
            "replay:run": [
                str(uuid)[:8] for uuid in latest.values_list("uuid", flat=True)[:20]
            ],
            "score:run": [str(run.uuid)[:8] for run in reversed(outstanding)],
        }

    @override
    def forget(self) -> None:
        super().forget()
        self._completions = None

    def say_cell(self) -> None:
        configuration = self.cell.label or "?"
        stack = self.cell.stack.name if self.cell.stack else "?"
        self.console.print(f"cell: {configuration} × {stack}")

    def say_refusals(self, refusals: Iterable[SliceRefusal]) -> None:
        for refusal in refusals:
            if refusal.kind == "later":
                self.console.print(
                    Text(f"not yet: {refusal.slice}: {refusal.reason}", style=LATER)
                )
            else:
                self.console.print(
                    Text(f"refused: {refusal.slice}: {refusal.reason}", style=REFUSED)
                )

    def error(self, message: str) -> None:
        self.console.print(Text(message, style=REFUSED))
