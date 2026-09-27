# pyright: basic
"""
A sampling variation as its page shows what it does: on each LLM the owner
runs on, for each reasoning its facts realize, what a request carries of
it, where the settings it leaves out come from, and what is refused; and
whether it is greedy, which leaves a batch's trials unseeded.
"""

from dataclasses import dataclass, field
from typing import Any

from chatddx.bench.bench import Bench, greedy
from chatddx.django.portal.records import said
from chatddx.repo.entities.reasoning.pydantic import INTENTS, ReasoningTrailBase
from chatddx.repo.entities.sampling.pydantic import SamplingTrailBase
from chatddx.runtime.resolution import realize


@dataclass(frozen=True)
class Realized:
    """What a sampling comes to on an LLM, reasoning any of the ways it does so."""

    llm: str
    # what the request carries of it, a setting each, and where what it
    # leaves out comes from
    writes: list[str] | None = None
    source: str | None = None
    # why it can't be sent so, where it can't
    refused: str | None = None
    greedy: bool = False
    # the reasonings it comes to this on, each with whether it is the LLM's default
    intents: list[tuple[str, bool]] = field(default_factory=list[tuple[str, bool]])


@dataclass(frozen=True)
class Realizing:
    """What a sampling comes to on each LLM, and whether it is greedy on all, some or none."""

    rows: list[Realized]

    @property
    def greedy(self) -> str:
        sent = [row.greedy for row in self.rows if row.refused is None]

        if sent and all(sent):
            return "all"

        return "some" if any(sent) else "none"


def realized_on(identity: str, sampling: SamplingTrailBase) -> Realizing:
    """The sampling on each LLM of the stacks the identity runs on, each reasoning it realizes."""
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

            # one row for the reasonings it comes to the same on
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
