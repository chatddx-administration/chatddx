# pyright: basic
"""What the API takes and gives beside the repo's, runtime's and pydantic-ai's."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from ninja import Schema
from pydantic import Field, JsonValue, StringConstraints, model_validator
from pydantic_ai.usage import RunUsage

from chatddx.bench.bench import MAX_SEED
from chatddx.repo.entities.case.pydantic import CaseTrailOut, TargetKind
from chatddx.repo.entities.client.pydantic import ClientTrailOut
from chatddx.repo.entities.configuration.pydantic import (
    ConfigurationBranchOut,
    ConfigurationTrailOut,
)
from chatddx.repo.entities.output.pydantic import View
from chatddx.repo.entities.reasoning.pydantic import ReasoningBranchOut
from chatddx.repo.entities.sampling.pydantic import SamplingTrailOut
from chatddx.repo.entities.scorer.pydantic import Metric, ScorerTrailOut
from chatddx.repo.entities.stack.pydantic import StackBranchOut, StackTrailOut
from chatddx.runtime.resolution import Coercion, Reasoning, Sampling, SliceRefusal, Tool

# where the case goes in the messages a cell is shown to make
CASE = "‹case›"

type Name = Annotated[str, StringConstraints(min_length=1)]

# a seed; none runs unseeded, and none given draws one, unless sampling is greedy
type Seed = Annotated[int, Field(ge=0, le=MAX_SEED)] | Literal["none"] | None


class Me(Schema):
    name: str
    guest: bool


class ScorerSum(Schema):
    scorer: str
    scores: int
    metrics: dict[Metric, float | None]
    without_value: int


class RunsWith(Schema):
    runs: int
    errored: int
    scorers: list[ScorerSum]


class Detail[B](Schema):
    """A branch, the identity's runs with it, and why a case's patterns don't parse."""

    branch: B
    runs: RunsWith
    unread: dict[TargetKind, str]


class CellIn(Schema):
    """
    A cell, as the repl holds one: a configuration, OWNER/NAME where another
    shares it, a stack, and any slice's variation set in place of the
    configuration's, `none` taking the toolset out.
    """

    configuration: Name | None = None
    stack: Name | None = None
    instruction: Name | None = None
    output: Name | None = None
    coercion: Name | None = None
    reasoning: Name | None = None
    sampling: Name | None = None
    toolset: Name | None = None


class ShowIn(CellIn):
    tag: list[Name] = Field(default_factory=list)


class SaveIn(CellIn):
    name: Name


class RunIn(CellIn):
    """A case, or a vignette of the client's own."""

    case: Name | None = None
    vignette: str | None = None
    seed: Seed = None
    stream: bool = True

    @model_validator(mode="after")
    def _a_case_or_a_vignette(self):
        if (self.case is None) == (self.vignette is None):
            raise ValueError("run a case, or a vignette: one of them")

        if self.vignette is not None and not self.vignette.strip():
            raise ValueError("a vignette says something")

        return self


class BatchIn(CellIn):
    """The cases with any of the tags, one after another, under one seed."""

    tags: list[Name] = Field(min_length=1)
    seed: Seed = None


class ScoreIn(Schema):
    run: str | None = None


class Page(Schema):
    limit: int = Field(20, ge=1, le=500)
    offset: int = Field(0, ge=0)


class Resolved(Schema):
    """How the cell resolves on its stack, a refused one as far as it goes."""

    refusals: list[SliceRefusal]
    reasoning: Reasoning | None
    sampling: Sampling | None
    greedy: bool
    coercion: Coercion | None
    tools: list[Tool]
    slots: dict[str, str]
    fields: dict[str, JsonValue] | None
    system: str | None
    user: str | None


class HeldTo(Schema):
    """Of the cases, how many a scorer can hold the cell to, and which it can't."""

    scorer: str
    view: View
    target_kind: TargetKind | None
    offered: bool
    have: int
    missing: list[str]
    unread: list[str]


class CellOut(Schema):
    """`set`: each slice's variation held in place of the configuration's, or none."""

    label: str | None
    configuration: ConfigurationBranchOut | None
    set: dict[str, Any]
    stack: StackBranchOut | None
    resolution: Resolved | None
    cases: int | None
    tags: list[str]
    scorers: list[HeldTo] | None


class Saved(Schema):
    what: Literal["created", "a new version", "unchanged"]
    copied: list[str]
    configuration: ConfigurationBranchOut


class Realization(Schema):
    reasoning: Reasoning | None
    sampling: Sampling | None
    refusals: list[SliceRefusal]


class StackRealizations(Schema):
    """Each variation on the stack, in the table's order."""

    stack: str
    current: bool
    realizations: list[Realization]


class ReasoningTable(Schema):
    """`sampling` and `current` are the cell's, the variation by its fingerprint."""

    sampling: SamplingTrailOut | None
    current: str | None
    variations: list[ReasoningBranchOut]
    stacks: list[StackRealizations]


class ScorerOut(Schema):
    """`offered`: whether the cell's output offers the view it reads."""

    name: str
    owner: str
    trail: ScorerTrailOut
    metrics: list[Metric]
    offered: bool | None


class ScoreOut(Schema):
    scorer: str
    scorer_fingerprint: str
    value: float | None
    answer: str | None
    reason: str | None
    target: str | None
    blob: str
    timestamp: datetime


class RunSummary(Schema):
    id: UUID
    trial: UUID
    timestamp: datetime
    description: str | None
    status: str
    valid: bool | None
    error: str | None
    scores: list[ScoreOut]


class BranchRow(Schema):
    id: int
    name: str
    owner: str


class ToolRan(BranchRow):
    blob: str


class ReadOut(Schema):
    """The branch rows whose details resolution read."""

    stack: BranchRow | None
    llm: BranchRow | None
    tools: list[ToolRan]


class RunOut(RunSummary):
    """`number`: the run's place among its trial's runs."""

    number: int
    started: datetime | None
    finished: datetime | None
    finish_reason: str | None
    answer: JsonValue
    views: dict[str, list[JsonValue]] | None
    configuration: ConfigurationTrailOut
    stack: StackTrailOut
    case: CaseTrailOut
    seed: int | None
    client: ClientTrailOut | None
    client_rev: str | None
    read: ReadOut


class TrialOut(Schema):
    id: UUID
    timestamp: datetime
    configuration: ConfigurationTrailOut
    stack: StackTrailOut
    case: CaseTrailOut
    seed: int | None
    runs: list[RunSummary]


class MessageOut(Schema):
    run: UUID
    role: str
    kind: str
    payload: dict[str, Any]
    timestamp: datetime


class Exchange(Schema):
    requests: list[str]
    responses: list[str]


class RunScored(Schema):
    run: RunSummary
    made: list[ScoreOut]
    unscored: Literal["errored", "no scorer applies", "scored already"] | None


class ScoringOut(Schema):
    runs: list[RunScored]
    summary: list[ScorerSum]


# A run streams pydantic-ai's own events as they come, by their `event_kind`,
# between these of the API's own, by their `type`.


class Batched(Schema):
    type: Literal["batch"] = "batch"
    description: str
    cases: list[str]
    seed: int | None


class Began(Schema):
    type: Literal["run"] = "run"
    run: UUID
    description: str
    case: str
    seed: int | None


class Answered(Schema):
    type: Literal["answer"] = "answer"
    answer: JsonValue
    usage: RunUsage


class Judged(Schema):
    """Whether the LLM reasoned as asked, and the answer held; what the views read."""

    type: Literal["judged"] = "judged"
    warning: str | None
    valid: bool | None
    problem: str | None
    views: dict[str, list[JsonValue]]
    # why the run was stopped short, its answer what came before
    stopped: str | None = None


class Failed(Schema):
    type: Literal["error"] = "error"
    message: str


class Scored(Schema):
    type: Literal["scores"] = "scores"
    scores: list[ScoreOut]


class Recorded(Schema):
    type: Literal["recorded"] = "recorded"
    run: RunOut


class Summarized(Schema):
    type: Literal["summary"] = "summary"
    runs: int
    scorers: list[ScorerSum]


type Event = Annotated[
    Batched | Began | Answered | Judged | Failed | Scored | Recorded | Summarized,
    Field(discriminator="type"),
]
