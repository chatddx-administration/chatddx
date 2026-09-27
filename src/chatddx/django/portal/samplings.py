# pyright: basic
from dataclasses import dataclass, field
from typing import Any

from chatddx.bench.bench import Bench, greedy
from chatddx.django.portal.records import said
from chatddx.repo.entities.reasoning.pydantic import INTENTS, ReasoningTrailBase
from chatddx.repo.entities.sampling.pydantic import SamplingTrailBase
from chatddx.runtime.resolution import realize


@dataclass(frozen=True)
class Realized:
    llm: str
    writes: list[str] | None = None
    source: str | None = None
    refused: str | None = None
    greedy: bool = False
    intents: list[tuple[str, bool]] = field(default_factory=list[tuple[str, bool]])


@dataclass(frozen=True)
class Realizing:
    rows: list[Realized]

    @property
    def greedy(self) -> str:
        sent = [row.greedy for row in self.rows if row.refused is None]

        if sent and all(sent):
            return "all"

        return "some" if any(sent) else "none"


def realized_on(identity: str, sampling: SamplingTrailBase) -> Realizing:
    bench = Bench(identity)
    llms: dict[int, tuple[str, Any, Any]] = {}

    for stack in bench.stacks():
        llm = stack.trail.llm

        if llm.id not in llms:
            llms[llm.id] = (
                bench.name_of("llm", llm),
                bench.facts_of(stack),
                stack.trail.serving,
            )

    rows: list[Realized] = []

    for name, facts, serving in sorted(llms.values(), key=lambda llm: llm[0]):
        realized = facts.reasoning.realized()
        previous: Realized | None = None

        for intent in INTENTS:
            if intent not in realized:
                continue

            row = _realized(
                name,
                *realize(ReasoningTrailBase(effort=intent), sampling, facts, serving),
            )
            default = facts.reasoning.default == intent

            if previous is not None and _same(previous, row):
                previous.intents.append((intent, default))
                continue

            row.intents.append((intent, default))
            rows.append(row)
            previous = row

    return Realizing(rows)


def _realized(llm: str, _reasoning: Any, pulled: Any, refusals: list[Any]) -> Realized:
    if pulled is None:
        return Realized(llm, refused="; ".join(refusal.reason for refusal in refusals))

    return Realized(
        llm,
        writes=[said({name: value}) for name, value in pulled.writes.items()],
        source=pulled.source,
        greedy=greedy(pulled),
    )


def _same(one: Realized, other: Realized) -> bool:
    return (one.writes, one.source, one.refused, one.greedy) == (
        other.writes,
        other.source,
        other.refused,
        other.greedy,
    )
