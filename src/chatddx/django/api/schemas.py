# pyright: basic
"""What the API takes and gives. An identity is given by name, never as its record."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from ninja import Schema
from pydantic import Field, JsonValue, StringConstraints, model_validator

from chatddx.repl.bench import MAX_SEED
from chatddx.repo.entities.case.pydantic import TargetKind
from chatddx.repo.entities.output.pydantic import View
from chatddx.repo.entities.scorer.pydantic import Metric
from chatddx.repo.entity_names import EntityName

# where the case goes in the messages a cell is shown to make
CASE = "‹case›"

type Name = Annotated[str, StringConstraints(min_length=1)]

# a seed; none runs unseeded, and none given draws one, unless sampling is greedy
type Seed = Annotated[int, Field(ge=0, le=MAX_SEED)] | Literal["none"] | None


class Me(Schema):
    name: str
    guest: bool


class Ref(Schema):
    """A trail, by the name of a branch of it the identity sees, or its fingerprint."""

    entity: EntityName
    name: str
    fingerprint: str


class Branch(Schema):
    entity: EntityName
    id: int
    name: str
    owner: str
    timestamp: datetime
    versions: int | None
    fingerprint: str
    trail: dict[str, Any]
    details: dict[str, Any]
    tags: list[str]
    collaborators: list[str]


class ScorerSum(Schema):
    scorer: str
    scores: int
    metrics: dict[Metric, float | None]
    without_value: int


class RunsWith(Schema):
    runs: int
    errored: int
    scorers: list[ScorerSum]


class TargetOut(Schema):
    """A case's target, neither part where missing; `unread`: why a pattern fails."""

    kind: TargetKind
    none_expected: bool
    text: str | None
    pattern: str | None
    unread: str | None


class BranchDetail(Branch):
    runs: RunsWith
    targets: list[TargetOut] | None


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


class Refusal(Schema):
    slice: str
    reason: str
    kind: Literal["refused", "later"]


class SliceOut(Schema):
    slice: str
    variation: Ref | None
    own: Ref | None
    set: bool


class StackOut(Schema):
    name: str
    owner: str
    fingerprint: str
    machine: Ref
    llm: Ref
    serving: Ref | None
    endpoint: str | None
    served_name: str | None
    api: str | None


class OutputOut(Schema):
    free_text: bool
    views: list[View]


class ReasoningOut(Schema):
    effort: str
    intent: str
    writes: dict[str, JsonValue]


class SamplingOut(Schema):
    """`greedy`: a temperature of 0 or a top-k of 1, which ignores a seed."""

    source: str
    writes: dict[str, JsonValue]
    greedy: bool


class CoercionOut(Schema):
    """`shown`: whether the LLM reads the schema through its slot."""

    requested: str
    mode: str
    shown: bool
    tool_description: str | None
    note: str | None
    sent: dict[str, JsonValue]


class ToolOut(Schema):
    name: str
    description: str
    parameters: dict[str, JsonValue]


class ResolutionOut(Schema):
    """How the cell resolves on its stack: a refused one as far as it goes."""

    resolved: bool
    refusals: list[Refusal]
    reasoning: ReasoningOut | None
    sampling: SamplingOut | None
    coercion: CoercionOut | None
    tools: list[ToolOut]
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
    label: str | None
    configuration: Ref | None
    configuration_owner: str | None
    slices: list[SliceOut]
    output: OutputOut | None
    stack: StackOut | None
    resolution: ResolutionOut | None
    cases: int | None
    tags: list[str]
    scorers: list[HeldTo] | None


class Saved(Schema):
    what: Literal["created", "a new version", "unchanged"]
    copied: list[str]
    configuration: Branch


class Realization(Schema):
    variation: str
    reasoning: ReasoningOut | None
    sampling: SamplingOut | None
    refusals: list[Refusal]


class StackRealizations(Schema):
    stack: str
    owner: str
    current: bool
    realizations: list[Realization]


class ReasoningVariation(Schema):
    name: str
    owner: str
    fingerprint: str
    effort: str
    budget: int | None
    current: bool


class ReasoningTable(Schema):
    """`sampling` is the cell's, which each variation pulls in."""

    sampling: Ref | None
    variations: list[ReasoningVariation]
    stacks: list[StackRealizations]


class ScorerOut(Schema):
    """`offered`: whether the cell's output offers the view it reads."""

    name: str
    owner: str
    fingerprint: str
    function: str
    view: str
    target_kind: str | None
    args: dict[str, JsonValue]
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


class ClientOut(Schema):
    build: str | None
    rev: str | None
    packages: dict[str, str]


class RunOut(RunSummary):
    """`number`: the run's place among its trial's runs."""

    number: int
    started: datetime | None
    finished: datetime | None
    finish_reason: str | None
    answer: JsonValue
    views: dict[str, list[JsonValue]] | None
    configuration: Ref
    slices: dict[str, Ref | None]
    stack: Ref
    case: Ref
    seed: int | None
    client: ClientOut | None
    read: ReadOut


class TrialOut(Schema):
    id: UUID
    timestamp: datetime
    configuration: Ref
    slices: dict[str, Ref | None]
    stack: Ref
    case: Ref
    vignette: str
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


# What a run streams as it goes, and its transcript repeats. A part is a piece
# of what the LLM sends back, numbered through the run: thinking, text, or a
# call to a tool, each of which may come in many events.


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


class Thought(Schema):
    """`in_content`: the thinking came in the answer's text."""

    type: Literal["thinking"] = "thinking"
    part: int
    text: str
    in_content: bool


class Wrote(Schema):
    type: Literal["text"] = "text"
    part: int
    text: str


class Called(Schema):
    type: Literal["call"] = "call"
    part: int
    tool: str
    arguments: str


class Returned(Schema):
    type: Literal["result"] = "result"
    tool: str
    content: str


class Used(Schema):
    type: Literal["usage"] = "usage"
    input_tokens: int
    output_tokens: int
    requests: int


class Warned(Schema):
    type: Literal["warning"] = "warning"
    message: str


class Judged(Schema):
    type: Literal["validity"] = "validity"
    valid: bool
    problem: str | None


class Viewed(Schema):
    type: Literal["views"] = "views"
    views: dict[str, list[JsonValue]]


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
    Batched
    | Began
    | Thought
    | Wrote
    | Called
    | Returned
    | Used
    | Warned
    | Judged
    | Viewed
    | Failed
    | Scored
    | Recorded
    | Summarized,
    Field(discriminator="type"),
]
