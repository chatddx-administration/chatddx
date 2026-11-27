from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, ClassVar, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from chatddx import catalog, settings
from chatddx.catalog.titles import CaseTitle as Titling
from chatddx.factors import base as factors
from chatddx.factors.cases import CleanupOp
from chatddx.factors.request import RECIPE_PARTS
from chatddx.factors.trial import Order
from chatddx.identity import Person, Role
from chatddx.runner import Outcome


class _Schema(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


type Code = Literal[
    "unauthenticated",
    "cross_site",
    "not_found",
    "not_allowed",
    "ambiguous",
    "conflict",
    "moved_on",
    "refused",
    "unprocessable",
    "over_quota",
    "whoops",
    "error",
]


class Error(_Schema):
    detail: str | list[JsonValue] = Field(
        description="why, or where a request doesn't validate"
    )
    code: Code
    pass_on: str | None = Field(
        default=None,
        description="a whoops's: what the person is to pass on to ops, as it is",
    )
    wording: str | list[str] | None = Field(
        default=None,
        description="a refusal's detail as written, its placeholders unfilled, or "
        + "singular and plural counted by params' num; null where the detail is all "
        + "there is",
    )
    params: dict[str, str | int | float] | None = Field(
        default=None, description="what fills its wording's placeholders"
    )

    @classmethod
    def of(cls, e: Exception, code: Code, detail: str | None = None) -> Self:
        if not isinstance(e, factors.Worded) or e.wording is None:
            return cls(detail=str(e) if detail is None else detail, code=code)
        return cls(
            detail=str(e) if detail is None else detail,
            code=code,
            wording=e.wording if isinstance(e.wording, str) else list(e.wording),
            params=dict(e.params),
        )


class SignIn(_Schema):
    login: str
    password: str


class Me(_Schema):
    id: int
    login: str
    name: str
    roles: list[Role]

    @classmethod
    def of(cls, person: Person) -> Self:
        return cls(
            id=person.id,
            login=person.login,
            name=person.name,
            roles=sorted(person.roles),
        )


class SignedIn(_Schema):
    token: str
    person: Me


class Labels(_Schema):
    views: list[str | None] = Field(
        default_factory=list[str | None], description="by position; null for none"
    )
    resources: list[str | None] = Field(
        default_factory=list[str | None], description="by position; null for none"
    )

    def given(self) -> catalog.Labels:
        parts: tuple[tuple[catalog.Part, list[str | None]], ...] = (
            ("view", self.views),
            ("resource", self.resources),
        )
        return {
            (part, position): label
            for part, labels in parts
            for position, label in enumerate(labels)
            if label is not None and label.strip()
        }

    @classmethod
    def of(cls, labels: Mapping[tuple[catalog.Part, int], str]) -> Self:
        def listed(part: catalog.Part) -> list[str | None]:
            held = {p: v for (k, p), v in labels.items() if k == part}
            return [held.get(p) for p in range(max(held, default=-1) + 1)]

        return cls(views=listed("view"), resources=listed("resource"))


class Edit(_Schema):
    id: int
    digest: str
    compilation: str | None
    based_on: int | None
    by: str
    at: datetime
    labels: Labels | None = Field(default=None, description="a scorer edit's")


class Versioned(Edit):
    version: int = Field(
        description="the version it holds, numbered by the first edit of its thread "
        + "to hold the same"
    )


class CaseTitle(_Schema):
    name: str = Field(description="its family's name, else its vignette's SOURCE/ID")
    appendices: list[str] = Field(description="its appendices' titles, in order")
    earlier: bool = Field(
        description="whether its vignette is an earlier one than its family's"
    )

    @classmethod
    def of(cls, titled: Titling) -> Self:
        return cls(
            name=titled.name, appendices=list(titled.appendices), earlier=titled.earlier
        )


class Thread(_Schema):
    id: int
    kind: str
    word: str = Field(description="the word for its kind: configuration for a skeleton")
    name: str | None
    title: str
    owner: str | None
    tags: list[str]
    language: str | None = Field(description="its head's")
    translated: list[str] = Field(
        description="a configuration's: the languages its head's translations carry it "
        + "into"
    )
    head: Edit
    outdated: bool = Field(
        description="whether its head can't be used until it is updated: it holds "
        + "weights its model's handle no longer holds, asks a judge that does, or "
        + "names an engine no endpoint here serves"
    )
    expecting: CaseTitle | None = Field(
        None,
        description="an expectation's with no name: the case it is for, by which it is "
        + "said",
    )


class ThreadDetail(Thread):
    description: str | None
    collaborators: list[str]
    forked_from: int | None
    recipe: JsonValue
    deleted: bool


class Said(_Schema):
    name: str | None = Field(
        None, description="null takes the name away, and the title takes over"
    )
    description: str | None = Field(None, description="null takes it away")
    tags: list[str] | None = Field(None, description="its tags")
    collaborators: list[str] | None = Field(
        None, description="the logins it is shared with"
    )
    deleted: bool | None = None


class FamilySaid(Said):
    language: str | None = Field(
        None, description="its vignette's: replaced, never taken away"
    )


type Chunk = Annotated[
    str | None,
    Field(description="a chunk's digest; empty or null takes an optional part out"),
]


type ModelDigest = Annotated[
    str | None, Field(description="a model's digest, which can't be taken out")
]


class Parts(_Schema):
    instructions: Chunk = None
    few_shot: Chunk = None
    prompt: Chunk = None
    output: Chunk = None
    sampling: Chunk = None
    reasoning: Chunk = None
    passthrough: Chunk = None
    translations: Chunk = None
    toolset: Chunk = None
    model: ModelDigest = None

    def given(self) -> dict[str, str | None]:
        return {
            p: getattr(self, p) or None
            for p in RECIPE_PARTS
            if p in self.model_fields_set
        }


class Varying(Parts):
    head: int | None = Field(
        None,
        description="the edit it varies, by id: the configuration's head unless given",
    )
    under: str | None = Field(
        None,
        description="the handle a hand-written configuration is rendered and linted "
        + "under; a configuration with a model part runs under its model's",
    )
    tag: list[str] = Field(
        default_factory=list[str],
        description="the cases its reach is over: any of these, else every one",
    )
    seed: int | None = Field(None, description="drawn when not given")


type ComponentBody = Annotated[
    dict[str, JsonValue],
    Field(
        description="a component's JSON as GET /api/components/{digest} gives its "
        + "body, kind included"
    ),
]
type RecipeBody = Annotated[
    dict[str, JsonValue],
    Field(
        description="a recipe's parts by digest, its purpose and its appendix layout, "
        + "as a configuration's recipe reads"
    ),
]
type Language = Annotated[
    str | None,
    Field(description="the language of the text the component holds, such as 'sv'"),
]


class NewThread(_Schema):
    component: ComponentBody | None = None
    recipe: dict[str, JsonValue] | None = Field(
        None,
        description="for a new configuration: the recipe's parts by digest, its "
        + "purpose and its appendix layout, as a configuration's recipe reads",
    )
    name: str | None = Field(
        None,
        min_length=1,
        description="none for an expectation alone, said by the case it is for",
    )
    language: Language = None
    labels: Labels | None = Field(None, description="for a scorer")

    @model_validator(mode="after")
    def _one(self) -> Self:
        if (self.component is None) == (self.recipe is None):
            raise ValueError("a new thread holds a component or a recipe, not both")
        return self


class NewFork(_Schema):
    name: str = Field(min_length=1)
    head: int | None = Field(
        None,
        description="a configuration's: the edit it forks from, its head unless given",
    )
    parts: Parts = Parts()
    component: ComponentBody | None = Field(
        None, description="what the fork starts from in place of the head"
    )
    language: Language = None
    labels: Labels | None = Field(
        None, description="for a scorer; a scorer forked as it is keeps the head's"
    )


class NewEdit(_Schema):
    head: int = Field(description="the edit the change was made on: the head seen")
    parts: Parts = Parts()
    component: ComponentBody | None = None
    language: Language = None
    labels: Labels | None = Field(
        None,
        description="for a scorer; without them, the head's when the scorer is the "
        + "head's, else none",
    )


type Drafted = Annotated[
    dict[str, ComponentBody | None],
    Field(
        description="chunks by part, each in place of the configuration's own; null "
        + "takes an optional part out"
    ),
]
type Into = Annotated[
    dict[str, dict[str, str]],
    Field(description="translations by language, each text to its translation"),
]


class Draft(_Schema):
    head: int | None = Field(
        None, description="the edit drafted on, the configuration's head unless given"
    )
    before: Drafted = Field(
        default_factory=dict,
        description="the draft the translations are given for, the edit's own unless "
        + "given",
    )
    after: Drafted = Field(default_factory=dict, description="the draft as it is now")
    translations: Into = Field(default_factory=dict)


class Drafting(_Schema):
    texts: dict[str, list[str]] = Field(
        description="the texts the draft holds, by part, as its translations key them"
    )
    translations: Into = Field(
        description="those given, carried over to the texts that changed in place"
    )


class Preview(_Schema):
    head: int | None = Field(
        None, description="the edit drafted on, the configuration's head unless given"
    )
    chunks: Drafted = Field(default_factory=dict)
    model: ModelDigest = None
    translations: Into | None = Field(
        None, description="all of them, by the texts drafted; without them its own"
    )
    language: str | None = Field(
        None,
        description="the language it is compiled into, as far as it is translated; "
        + "its own unless given",
    )


class Stretch(_Schema):
    text: str | None = Field(
        default=None, description="a run of text, or else a slot's"
    )
    origin: str | None = Field(default=None, description="the part the text came from")
    untranslated: bool = Field(
        default=False, description="the text as written, for want of a translation"
    )
    slot: str | None = None
    appendix: int | None = Field(
        default=None, description="the appendix of the placeholders, counted from 1"
    )


class PreviewMessage(_Schema):
    role: str
    runs: list[Stretch]


class Previewed(_Schema):
    messages: list[PreviewMessage] = Field(
        description="the messages as read, the appendices laid out as placeholders"
    )
    request: dict[str, JsonValue] = Field(
        description="the request as sent, without a seed or return_token_ids"
    )
    contract: dict[str, JsonValue] = Field(description="how the answer is held")


class NewSave(_Schema):
    head: int = Field(description="the edit the change was made on")
    name: str | None = Field(
        None, min_length=1, description="a fork's: without it, a version is saved"
    )
    independent: bool = Field(
        False,
        description="with a name, a configuration of its own, forked from nothing",
    )
    chunks: Drafted = Field(default_factory=dict)
    model: ModelDigest = None
    translations: Into | None = Field(
        None,
        description="all of them, by the texts as saved; without them its own, carried "
        + "over to the texts that changed in place",
    )


class Part(_Schema):
    part: str
    digest: str | None
    title: str | None
    summary: str | None
    replaced: bool
    landed: str | None = Field(
        None,
        description="a reasoning level's, or the one a recommended sampling follows: "
        + "the level the engine's model is asked for",
    )
    nearest: list[str] = Field(
        default_factory=list[str],
        description="why the level asked for landed on its nearest instead",
    )


class Finding(_Schema):
    level: Literal["info", "warning"]
    code: str
    message: str
    subject: str | None
    wording: str | list[str] | None = Field(
        description="the message as written, its placeholders unfilled, or singular "
        + "and plural counted by params' num; null where the message is all there is"
    )
    params: dict[str, str | int | float] = Field(
        description="what fills its wording's placeholders"
    )

    @classmethod
    def of(cls, finding: factors.Finding) -> Self:
        return cls.model_validate(finding.model_dump())


class Varied(_Schema):
    path: str
    base: JsonValue
    fork: JsonValue


class Remodelled(_Schema):
    was: str = Field(description="the model its base is made for, by name")
    now: str = Field(description="the model its origin's head is made for, by name")


class Proposal(_Schema):
    reasons: list[Literal["origin", "facts", "model", "judge", "engine"]] = Field(
        description="why it is behind what it was made from: its origin moved on, the "
        + "facts about its model were corrected where they change what it sends, its "
        + "model has a new version, a judge it asks is behind, or no endpoint here "
        + "serves its engine; the last three leave it unusable until it is updated"
    )
    about: str | None = Field(
        description="for a configuration or a judge, the model its head is made for, "
        + "by name"
    )
    base: Edit | None = Field(
        description="when its origin moved on, the version of its origin it is "
        + "compared with"
    )
    origin_head: Edit | None
    varies: list[Varied] = Field(description="what its head changes of its base")
    clashes: list[str] = Field(
        description="the paths it and its origin both change, each its own way: "
        + "updating keeps its own"
    )
    remodelled: Remodelled | None = Field(
        description="when its origin moved to another model, which updating moves it to"
    )
    recipe: JsonValue = Field(description="for a configuration, what it compiles from")
    component: JsonValue = Field(description="for another kind, its body")
    digest: str | None = Field(description="what updating comes to")
    compilation: str | None
    refused: str | None = Field(description="why updating is refused")


class Kin(Thread):
    origin: int | None = Field(
        description="the thread it is a fork of; null for the first of the lineage"
    )
    base: Edit | None = Field(
        description="a fork's: the version of its origin it is compared with"
    )
    varies: list[Varied] = Field(description="a fork's: what its head changes")
    behind: bool = Field(
        description="it is behind what it was made from, so updating it is proposed"
    )
    deleted: bool


class NewUpdate(_Schema):
    head: int = Field(description="the edit the change was made on: the head seen")
    language: Language = None


class MadeThread(ThreadDetail):
    findings: list[Finding]


class MadeEdit(Edit):
    findings: list[Finding]
    cases: dict[str, str] = Field(
        default_factory=dict,
        description="for an appendix: each case that held the old version, with its "
        + "replacement",
    )


class Reach(_Schema):
    scorer: int
    name: str
    view: int
    label: str
    offered: bool
    cases: int
    missing: list[int]
    choosing: list[int]


class Carried(_Schema):
    language: str | None = Field(
        description="the cases' language; null for the configuration's own when it is "
        + "unknown"
    )
    families: list[int]
    translated: bool
    skeleton: str | None = Field(description="the request they are sent as")
    refused: str | None = Field(description="why they can't be sent, and are left out")
    untranslated: bool = Field(
        description="whether they are left out as the configuration has no "
        + "translations into their language"
    )


class Variation(_Schema):
    head: Edit
    label: str = Field(description="its name, and the chunks it replaces")
    skeleton: str
    held_by: Thread | None = Field(
        description="the configuration whose head is the skeleton, the person's own first"
    )
    greedy: bool
    parts: list[Part] | None
    seed: int
    request: dict[str, JsonValue]
    model: str | None = Field(description="the handle it runs under")
    problem: str | None = Field(
        description="why it can't run: its handle doesn't resolve, which is ops' to "
        + "mend, it is out of date, or it names no model"
    )
    findings: list[Finding] | None
    languages: list[Carried] = Field(
        description="the languages its cases are sent in, the configuration's own "
        + "first, and those it can't be sent in"
    )
    reach: list[Reach]


class Family(_Schema):
    id: int
    name: str
    owner: str | None
    tags: list[str]
    language: str | None
    case: str


class Expected(_Schema):
    expectation_schema: str
    title: str
    expectation: str | None
    data: JsonValue
    ambiguous: str | None
    shared: list[Thread] = Field(
        description="the expectation threads of others, shared with the person, they "
        + "could take"
    )


class NewTakes(_Schema):
    families: list[int] = Field(min_length=1, description="the cases, by family")
    expectation_schema: str
    owner: str | None = Field(None, description="a login: that owner's only")


class Taken(_Schema):
    taken: dict[int, int] = Field(description="the thread each was taken into")
    kept: dict[int, int] = Field(description="the person's own, left as it is")
    choosing: dict[int, list[int]] = Field(
        description="shared by several owners: the threads to choose from"
    )
    missing: list[int] = Field(description="none shared")


class NewTake(_Schema):
    replace: bool = Field(
        False,
        description="delete the person's own expectation of the case under that "
        + "schema, in the same write",
    )


class NewTyped(_Schema):
    text: str = Field(description="the case as typed, kept as written")
    name: str | None = None
    language: str = Field(description="the language it is typed in, such as 'sv'")
    source: str | None = Field(
        None,
        description="the database source it is kept in, when the World has several",
    )


class NewAppendix(_Schema):
    text: str = Field(min_length=1)
    name: str = Field(min_length=1)


class FamilyCase(_Schema):
    case: str
    title: str
    titled: CaseTitle
    appendices: list[str]
    default: bool = Field(description="the case the family stands for")
    expectations: list[Expected]


class NewCase(_Schema):
    appendices: list[str] | None = Field(None, description="the appendices, in order")
    replacing: str | None = Field(
        None, description="or a case of the family left at an earlier vignette"
    )

    @model_validator(mode="after")
    def _one(self) -> Self:
        if (self.appendices is None) == (self.replacing is None):
            raise ValueError(
                "a case is built from appendices or replacing one, not both"
            )
        return self


class FamilyDetail(Family):
    description: str | None
    collaborators: list[str]
    deleted: bool
    cases: list[FamilyCase] = Field(
        description="its cases at its current vignette, the one it stands for first"
    )


class Vignette(_Schema):
    source: str
    id: str
    text: str
    drifted: bool | None


class Endpoint(_Schema):
    name: str
    engine: str
    title: str | None
    model: str | None
    serves: str | None = Field(description="the model its engine serves, by digest")
    url: str
    host: str | None
    capacity: int
    credential: str | None
    cleared_for: list[str]
    takes_typed: bool = Field(
        description="whether a case typed into the World's database source can run "
        + "here: the source isn't sensitive, or the endpoint is cleared for it"
    )
    problem: str | None


class Component(_Schema):
    digest: str
    kind: str
    title: str
    body: JsonValue


class Kind(_Schema):
    kind: str
    word: str = Field(description="the bench's word for it, as GET /api/threads takes")
    written: bool = Field(description="whether a person writes it")
    json_schema: dict[str, JsonValue] = Field(
        description="its JSON Schema; a reference names the kinds it takes in x-kind"
    )


class Checked(_Schema):
    digest: str
    findings: list[Finding]


class Metric(_Schema):
    name: str
    measures: str
    params: dict[str, JsonValue] = Field(
        description="a JSON Schema for a view's params"
    )
    judged: bool = Field(
        description="whether it reads a judge's verdicts, so that its view names a judge"
    )
    unit: str | None = Field(
        default=None,
        description="what marks a value that isn't a score from 0 to 1, as @ an offset",
    )


class ScorerCode(_Schema):
    entry_point: str
    version: int
    metrics: list[Metric]
    params: dict[str, JsonValue] = Field(
        description="a JSON Schema for the scorer's own params, which every view shares"
    )


class Picking(_Schema):
    document: JsonValue = Field(
        description="what the selectors pick from, such as an expectation's data"
    )
    selectors: list[str] = Field(
        description="each a JSON Pointer, or a JSONPath query of the subset a view takes"
    )


class Picked(_Schema):
    items: list[JsonValue] | None = Field(
        description="what the selector picks, in the document's order; null when it "
        + "doesn't read"
    )
    problem: str | None = Field(description="why the selector doesn't read")


class Trying(_Schema):
    scorer: ComponentBody = Field(description="a scorer, as it is written")
    expectation: JsonValue = Field(description="what it is scored against, its data")
    case: str = Field(description="the case whose items are tried")
    runs: list[UUID] = Field(
        min_length=1, max_length=50, description="the runs whose items are tried"
    )


class TriedView(_Schema):
    value: float | None
    detail: JsonValue
    judged: bool = Field(
        description="a view its judge scores, which isn't tried: its value is null"
    )


class Tried(_Schema):
    run: UUID
    replicate: int
    views: list[TriedView]


class Measuring(_Schema):
    case: str = Field(description="the case whose answers are read")
    expectation_schema: str = Field(
        description="the schema the expectation is written to, by digest"
    )
    data: JsonValue = Field(description="the expectation's data, as it is written now")
    field: str = Field(
        description="the field measured: each view of a scorer under the schema that "
        + "reads it scores what it picks of each answer against the data"
    )


class MeasuredMark(_Schema):
    item: int
    start: int
    end: int


class MeasuredSeen(_Schema):
    run: UUID
    at: datetime
    replicate: int
    configuration: str
    view: str = Field(description="the scorer's title and the view's label")
    href: str | None = Field(description="the page of the score stored for it")


class MeasuredText(_Schema):
    texts: list[str] | None = Field(
        description="what the views pick of the answers, alike in each of them"
    )
    marks: list[MeasuredMark]
    found: bool | None = Field(
        description="null when nothing was picked, for want of an answer or a target"
    )
    value: float | None
    unit: str
    reason: str | None
    count: int = Field(description="how many times the views scored it")
    alternatives: list[int] = Field(
        description="the pattern's alternatives that find it, by position"
    )
    seen: list[MeasuredSeen] = Field(
        description=f"where, the latest {settings.ROWS_PER_PAGE} at most"
    )


class MeasuredAlternative(_Schema):
    pattern: str
    found: int = Field(description="how many of what was found it finds")


class Measured(_Schema):
    pattern: str | None
    problem: str | None = Field(
        description="why the pattern doesn't read, if it doesn't"
    )
    answers: int = Field(description="how many answers the views read")
    found: int
    missed: int
    unscored: int
    alternatives: list[MeasuredAlternative] = Field(
        description="each alternative of the pattern's, at its top level"
    )
    texts: list[MeasuredText] = Field(
        description="missed first, then not scored, then found, each the most often "
        + "scored first"
    )


class FaredBehind(_Schema):
    why: Literal[
        "under_way",
        "outdated",
        "untranslated",
        "refused",
        "no_runs",
        "not_whole",
        "changed",
        "halted",
        "unfinished",
        "unscored",
    ]
    refusal: Error | None = Field(default=None, description="a refused's refusal")
    language: str | None = Field(
        default=None, description="an untranslated's language, by tag"
    )


class FaredConfiguration(_Schema):
    id: int
    name: str
    behind: list[FaredBehind] = Field(
        description="what keeps the case's latest gathering under it from being a "
        + "whole 3+1 as things are now, empty when it is one"
    )


class FaredMetric(_Schema):
    scorer: str
    view: int
    label: str = Field(description="the scorer's title and the view's label")
    field: str | None = Field(description="the expectation's field the view reads")


class FaredCase(_Schema):
    case: str
    family: int
    title: str


class FaredReplicate(_Schema):
    value: float | None = Field(description="null where it wasn't scored")
    href: str | None = Field(description="the page of its score, null where drawn")


class FaredShown(_Schema):
    value: float
    synthetic: bool
    replicates: list[FaredReplicate] = Field(
        description="each replicate the value is the mean of, as they ran"
    )


class FaredRow(_Schema):
    metric: int = Field(description="its metric, by position")
    configuration: int = Field(description="its configuration, by position")
    cases: list[int] = Field(description="the other cases, by position")
    values: list[float] = Field(description="each other case's mean, alike in order")
    synthetic: list[bool] = Field(description="whether each was drawn, alike in order")
    shown: FaredShown | None = Field(description="the case asked about, if it has one")


class Fared(_Schema):
    synthetic: bool = Field(description="whether any value is drawn rather than run")
    run: bool = Field(
        description="whether a run of the case has something to do: nothing of it is "
        + "under way and a configuration is behind in a way a run mends"
    )
    configurations: list[FaredConfiguration]
    metrics: list[FaredMetric]
    cases: list[FaredCase]
    rows: list[FaredRow]


class Asking(_Schema):
    judge: str = Field(description="a stored judge, by digest")
    expectation: str = Field(description="what a view picks of the expectation")
    data: JsonValue = Field(description="the expectation's data")


class Asked(_Schema):
    request: dict[str, JsonValue] = Field(
        description="the judge's first request, the answer a placeholder"
    )
    picked: list[JsonValue] = Field(description="what the view picks of the data")


class Seeds(_Schema):
    seeds: list[int] | None = Field(
        default=None,
        min_length=1,
        max_length=settings.ITEMS_PER_RUN,
        description="the replicates' seeds",
    )
    replicates: int | None = Field(
        default=None,
        ge=1,
        le=settings.ITEMS_PER_RUN,
        description="or how many replicates, their seeds drawn",
    )

    @model_validator(mode="after")
    def _seeds_or_replicates(self) -> Self:
        if self.seeds is not None and self.replicates is not None:
            raise ValueError("a run takes seeds or replicates, not both")
        return self


class NewAgain(Seeds):
    score: bool = Field(
        True, description="under every scorer that applies, once it is finished"
    )


class NewRun(Seeds):
    configuration: int
    head: int | None = Field(
        None,
        description="the edit it varies, by id: the configuration's head unless given",
    )
    parts: Parts = Parts()
    under: str | None = Field(
        None,
        description="the handle a hand-written configuration runs under; a "
        + "configuration with a model part runs under its model's",
    )
    families: list[int] | None = Field(
        None, min_length=1, description="the cases to run, by family"
    )
    tags: list[str] | None = Field(
        None, description="or the cases of the families with any of these"
    )
    cases: list[str] | None = Field(
        None,
        min_length=1,
        description="or the cases themselves, each of a family's current ones",
    )
    cleanup: list[CleanupOp] | None = Field(
        None,
        description="the steps applied to each vignette, in order: its source's when "
        + "not given, and none for []",
    )
    concurrency: int | None = Field(
        None,
        ge=1,
        description="how many requests at once, up to the endpoint's capacity: the "
        + "endpoint's when not given",
    )
    order: Order | None = Field(
        None,
        description="the order the items are sent in, a shuffled one's seed drawn: the "
        + "endpoint's when not given",
    )
    score: bool = Field(
        True, description="under every scorer that applies, once it is finished"
    )

    @model_validator(mode="after")
    def _cases(self) -> Self:
        if [self.families, self.tags, self.cases].count(None) != 2:
            raise ValueError("a run takes one of families, tags or cases")
        return self


class NewTrialRuns(_Schema):
    trials: list[int] = Field(
        min_length=1,
        description="the trials' versions to run, by edit id, as one start",
    )
    concurrency: int | None = Field(
        None,
        ge=1,
        description="how many requests at once, up to each endpoint's capacity: each "
        + "endpoint's when not given",
    )
    order: Order | None = Field(
        None,
        description="the order the items are sent in, a shuffled one's seed drawn: "
        + "each endpoint's when not given",
    )
    score: bool = Field(
        True, description="under every scorer that applies, once it is finished"
    )


class Rig(_Schema):
    distribution: str
    version: str
    revision: str | None


class Unscored(_Schema):
    scorer: str
    name: str


class RunJob(_Schema):
    status: Literal["queued", "under way", "finished", "stopped", "failed"]
    why: str | None = Field(
        description="why it stands as it does: a failure, or why it was queued again "
        + "or stopped"
    )
    halt: bool = Field(description="whether it was asked to halt")
    ahead: int | None = Field(
        description="while queued, the jobs at its endpoint under way or to be taken "
        + "before it; null while its owner has paused, and once it is taken"
    )
    queued: datetime
    ended: datetime | None


class Replaced(_Schema):
    part: str
    title: str | None = Field(description="what it holds instead; null for nothing")


class Titled(_Schema):
    name: str = Field(
        description="what it ran: its configuration's name, else the run's own"
    )
    replaced: list[Replaced] = Field(
        description="what its variation replaced, but the model it ran under"
    )
    at: str = Field(
        description="what it ran under: its handle, else its endpoint or its engine"
    )
    case: CaseTitle | None = Field(description="its case's title, when it ran one")
    cases: int
    translated: str | None = Field(
        description="the language its request was translated into, when it was"
    )
    greedy: bool
    seeds: list[int]


class Ran(_Schema):
    configuration: int
    head: int = Field(description="the edit it varied")
    parts: dict[str, str | None] = Field(
        description="each part replaced over it: a chunk's digest, or null for one "
        + "taken out"
    )


class Run(_Schema):
    id: UUID
    at: datetime
    trial: str
    skeleton: str
    language: str | None = Field(description="the language its request is sent in")
    started_with: UUID | None = Field(
        description="the first run of the start it is one of; null for the first, and "
        + "for a run started alone"
    )
    engine: str
    endpoint: str | None
    model: str | None = Field(
        description="the handle its weights are under; null when they are under none"
    )
    latest: bool = Field(description="whether it ran at its handle's latest engine")
    cases: list[str]
    seeds: list[int]
    described: str
    titled: Titled
    ran: Ran | None = Field(
        description="the variation it ran, as it was started; null for a run started "
        + "from a trial alone"
    )
    finished: bool
    unscored: list[Unscored] | None = Field(
        default=None,
        description="with `unscored`: the scorers it is left to be scored by",
    )
    job: RunJob | None = Field(
        default=None, description="its latest job; null for a run no job took"
    )


class Item(_Schema):
    case: str
    replicate: int
    outcome: Outcome
    prompt_tokens: int
    completion_tokens: int


class Answer(_Schema):
    value: JsonValue = Field(
        description="as read from the item's last call: what its schema holds, or text"
    )
    problem: str | None = Field(
        description="why it couldn't be read, or breaks its schema"
    )
    salvaged: bool = Field(
        description="a structured answer cut short, read with its structure closed"
    )


class ItemDetail(Item):
    why: str | None
    vignette: JsonValue
    call: JsonValue
    turns: JsonValue
    answer: Answer


class ComparedView(_Schema):
    scorer: str
    name: str
    view: int
    label: str
    means: list[float | None] = Field(
        description="each run's mean over the items it has a value for, in the order "
        + "the runs are given"
    )
    values: list[list[float | None]] = Field(
        description="each run's value for each item, in the order the items are"
    )


class ItemKey(_Schema):
    case: str
    replicate: int


class HeldBySome(_Schema):
    case: str
    runs: list[UUID] = Field(description="the runs that hold it")


class Compared(_Schema):
    runs: list[Run]
    views: list[ComparedView] = Field(
        description="each view of each scorer that scored one of the runs, by its name"
    )
    items: list[ItemKey] = Field(description="the items every run's trial holds")
    apart: list[HeldBySome] = Field(description="the cases only some of the runs hold")


class ScoredItem(_Schema):
    case: str
    replicate: int
    view: int
    value: float | None


class Graded(_Schema):
    scorer: str
    name: str
    score: UUID | None
    scoring: str | None
    at: datetime | None
    finished: bool
    labels: list[str]
    means: list[float | None]
    items: list[ScoredItem]
    refused: str | None


class ScoreItemDetail(ScoredItem):
    detail: JsonValue
    judge_calls: JsonValue


class ScoreItems(_Schema):
    items: list[ScoreItemDetail]
    findings: list[Finding]


class RunDetail(Run):
    rig: Rig
    finished_at: datetime | None
    noted: list[Finding]
    findings: list[Finding]
    items: list[Item]
    scores: list[Graded]


class RenderedAgain(_Schema):
    case: str
    replicate: int
    same: bool
    why: str | None


class NewResume(_Schema):
    score: bool = Field(
        default=True, description="under every scorer that applies, once it is finished"
    )


class Paused(_Schema):
    paused: bool


class NewStop(_Schema):
    now: bool = Field(
        default=False,
        description="halt the runs under way too, as a second press of stop does",
    )


class Queue(_Schema):
    paused: bool
    queued: int = Field(description="the person's jobs queued")
    under_way: int = Field(description="the person's jobs under way")
    workers: int = Field(
        description="the workers seen lately, whoever's jobs they hold"
    )


class Stopped(_Schema):
    taken_out: list[UUID] = Field(
        description="the runs whose queued jobs ended stopped, left as they were"
    )
    halting: list[UUID] = Field(description="the runs under way asked to halt")


class NewScoring(_Schema):
    scorers: list[str] | None = Field(
        None, description="by digest; every scorer that applies when not given"
    )


class RunStartedData(_Schema):
    run: UUID
    trial: str
    skeleton: str
    language: str | None = Field(description="the language its request is sent in")
    endpoint: str | None
    cases: list[str]
    seeds: list[int]
    greedy: bool


class LeftOut(_Schema):
    language: str
    cases: list[str]
    why: str


class StartedRuns(_Schema):
    runs: list[RunStartedData] = Field(
        description="a run per language its cases are sent in: the configuration's "
        + "own first, as written, then each it is translated into"
    )
    left_out: list[LeftOut] = Field(
        description="the cases of each language the configuration can't be sent in"
    )


class ItemStartedData(_Schema):
    case: str
    replicate: int
    seed: int


class ItemDeltaData(_Schema):
    case: str
    replicate: int
    kind: Literal["reasoning", "content", "tool_call"]
    text: str
    tokens: int


class ItemToolData(_Schema):
    case: str
    replicate: int
    tool: JsonValue


class ItemEndedData(Item):
    why: str | None


class CanaryEndedData(_Schema):
    phase: str
    canary: int
    call: JsonValue


class RunFinishedData(_Schema):
    findings: list[Finding]


class ScoringData(_Schema):
    scorers: list[Unscored]


class ScoreStartedData(_Schema):
    scorer: str
    name: str
    score: UUID
    labels: list[str]


class ScoreItemData(ScoredItem):
    score: UUID
    detail: JsonValue


class JudgeAskedData(_Schema):
    case: str
    replicate: int
    scorer: str
    view: int
    judge: str
    seed_index: int


class JudgeDeltaData(_Schema):
    case: str
    replicate: int
    kind: Literal["reasoning", "content", "tool_call"]
    text: str
    tokens: int


class JudgeAnsweredData(_Schema):
    case: str
    replicate: int
    view: int
    judge: str
    seed_index: int
    verdict: JsonValue
    call: JsonValue


class RunScoredData(_Schema):
    scores: list[Graded]


class ErrorData(_Schema):
    detail: str


class DoneData(_Schema):
    halted: bool | None = Field(
        description="whether the run's last job was asked to halt; null when the run "
        + "had none"
    )


EVENTS: dict[str, type[_Schema]] = {
    "run.started": RunStartedData,
    "item.started": ItemStartedData,
    "item.delta": ItemDeltaData,
    "item.tool": ItemToolData,
    "item.ended": ItemEndedData,
    "canary.ended": CanaryEndedData,
    "run.noted": Finding,
    "run.finished": RunFinishedData,
    "run.scoring": ScoringData,
    "score.started": ScoreStartedData,
    "judge.asked": JudgeAskedData,
    "judge.delta": JudgeDeltaData,
    "judge.answered": JudgeAnsweredData,
    "score.item": ScoreItemData,
    "score.noted": Finding,
    "run.scored": RunScoredData,
    "error": ErrorData,
    "done": DoneData,
}


class BrokenView(_Schema):
    scorer: str
    view: int
    label: str = Field(description="the scorer's title and the view's label")
    field: str | None = Field(description="the expectation's field the view reads")


class Estimated(_Schema):
    mean: float
    half: float | None = Field(
        description="the half-width of its 95% interval, none for one value"
    )
    n: int


class BrokenLanguage(_Schema):
    language: str | None
    cases: int


class BrokenPoint(_Schema):
    started: UUID = Field(description="the gathering's first run")
    at: datetime
    version: int = Field(description="the configuration's version, from 1")
    means: list[float | None] = Field(description="by view, its replicates' mean")
    spread: list[float | None] = Field(
        description="by view, how far its repeats' values were from its replicates'"
    )
    alike: int = Field(description="answers its repeats gave alike to the letter")
    compared: int = Field(description="answers its repeats were compared on")
    languages: list[BrokenLanguage]
    failed: float = Field(description="the share of its items whose call failed")
    seconds: float = Field(description="an item's mean time")
    tokens: float | None = Field(description="an item's mean answer tokens")
    stale: bool = Field(description="not all of it scored as things are now")
    missing: int = Field(
        description="the baseline cases, as they are now, none of its replicates "
        + "answered without failing"
    )


class BrokenGathering(_Schema):
    digest: str = Field(description="the skeleton it ran")
    point: BrokenPoint
    estimates: list[Estimated | None] = Field(description="by view, over its cases")
    values: list[list[float]] = Field(description="by view, each case's value, sorted")
    paired: list[Estimated | None] = Field(
        description="by view, its mean difference from the gathering before, case by "
        + "case on the cases both sent"
    )


class GatheredValue(_Schema):
    value: float
    score: UUID = Field(description="the score it is read from")


class GatheredRun(_Schema):
    run: UUID
    language: str | None
    repeat: bool = Field(description="whether it is the repeat, else the original")


class GatheredCase(_Schema):
    case: str
    language: str | None = Field(description="the language it went in")
    answered: bool = Field(description="whether its replicate answered without failing")
    alike: bool | None = Field(
        description="whether its repeat answered alike to the letter; null where "
        + "either said nothing"
    )
    replicate: list[GatheredValue | None] = Field(description="by view")
    repeat: list[GatheredValue | None] = Field(description="by view")
    before: list[float | None] = Field(
        description="by view, the gathering before's value"
    )


class Gathering(_Schema):
    configuration: int
    name: str
    tag: str
    cases: int = Field(description="the World's baseline cases now")
    views: list[BrokenView]
    gathering: BrokenGathering
    before: BrokenGathering | None = Field(
        description="the configuration's baseline gathering before it"
    )
    runs: list[GatheredRun]
    rows: list[GatheredCase] = Field(
        description="each case it sent or the baseline holds now, those first"
    )


class BrokenPeer(_Schema):
    id: int
    name: str
    means: list[float | None] = Field(
        description="by view, its latest baseline's mean, none where not shared"
    )
    point: BrokenPoint


class Broken(_Schema):
    name: str
    tag: str
    cases: int
    views: list[BrokenView]
    gatherings: list[BrokenGathering] = Field(description="in the order they ran")
    peers: list[BrokenPeer]
