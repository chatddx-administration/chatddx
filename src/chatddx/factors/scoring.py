import json
from collections.abc import Sequence
from typing import Annotated, ClassVar, Literal, override

from pydantic import AfterValidator, Field, JsonValue

from .base import (
    Component,
    Digest,
    Frozen,
    RefTo,
    Resolver,
    Settings,
    StructuralError,
    ascending,
    distinct,
    resolve,
)
from .cases import CaseRef
from .engine import EngineRef, ModelRef, model_of
from .request import EntryPoint, Skeleton, SkeletonRef, SlotName
from .select import (
    SplitOp,
    check_selector,
    parse_selector,
    reaches,
    reaches_text,
    select,
    split,
)


class ExpectationSchema(Component):
    kind: Literal["expectation_schema"] = "expectation_schema"
    json_schema: dict[str, JsonValue]


ExpectationSchemaRef = Annotated[Digest, RefTo("expectation_schema")]


class Expectation(Component):
    kind: Literal["expectation"] = "expectation"
    case: CaseRef
    expectation_schema: ExpectationSchemaRef
    data: JsonValue


ExpectationRef = Annotated[Digest, RefTo("expectation")]

# Policy: how a judge's slots are written out, one name per behavior as with CleanupOp
# (cases.py).
FillOp = Literal["text@1"]


def fill_text(op: FillOp, items: Sequence[JsonValue]) -> str:
    assert op == "text@1"
    value: JsonValue = items[0] if len(items) == 1 else list(items)
    match value:
        case str():
            return value
        case list() if all(isinstance(v, str) for v in value):
            return "\n".join(str(v) for v in value)
        case _:
            return json.dumps(value, indent=2, ensure_ascii=False)


class Judge(Component):
    kind: Literal["judge"] = "judge"
    schema_version: ClassVar[int] = 2
    skeleton: SkeletonRef
    model: ModelRef
    seeds: Annotated[tuple[int, ...], AfterValidator(distinct)] = Field(min_length=1)
    fill: FillOp = "text@1"

    @override
    def cross_check(self, get: Resolver) -> list[str]:
        skeleton = resolve(get, self.skeleton, Skeleton)
        if skeleton.purpose != "judge":
            return [f"judge uses a {skeleton.purpose} skeleton"]
        if skeleton.tools:
            return ["judge uses a skeleton with tools, which a judge can't run"]
        return []

    def fills(
        self, view: "View", answer: JsonValue, expectation: JsonValue
    ) -> dict[SlotName, str]:
        if view.judge != self.digest:
            raise StructuralError(f"the view is judged by {view.judge}, not this judge")
        return {
            "completion": fill_text(self.fill, view.output_items(answer)),
            "expectation": fill_text(self.fill, view.expectation_items(expectation)),
        }


JudgeRef = Annotated[Digest, RefTo("judge")]


Selector = Annotated[str, AfterValidator(check_selector)]


class View(Frozen):
    output: Selector = ""
    expectation: Selector = ""
    split: SplitOp | None = None
    metric: str
    judge: JudgeRef | None = None
    params: Settings = Field(default_factory=dict)

    def output_items(self, answer: JsonValue) -> list[JsonValue]:
        items = select(answer, self.output)
        return items if self.split is None else split(self.split, items)

    def expectation_items(self, data: JsonValue) -> list[JsonValue]:
        return select(data, self.expectation)

    def offered_by(self, schema: JsonValue) -> bool:
        if not parse_selector(self.output):
            return schema is None
        # Policy: a view no judge reads picks text, so one whose selector reaches only
        # objects or arrays isn't offered: a pattern would read their JSON, and match
        # what a field beside the one meant says.
        if self.judge is None:
            return reaches_text(schema, self.output)
        return reaches(schema, self.output)


class Scorer(Component):
    kind: Literal["scorer"] = "scorer"
    schema_version: ClassVar[int] = 2
    entry_point: EntryPoint
    version: int = Field(ge=1)
    expectation_schema: ExpectationSchemaRef
    views: tuple[View, ...] = Field(min_length=1)
    resources: tuple[str, ...] = ()
    params: Settings = Field(default_factory=dict)

    @property
    def judges(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(v.judge for v in self.views if v.judge is not None))


ScorerRef = Annotated[Digest, RefTo("scorer")]


class JudgeEngine(Frozen):
    judge: JudgeRef
    engine: EngineRef


class Scoring(Component):
    kind: Literal["scoring"] = "scoring"
    schema_version: ClassVar[int] = 2
    scorer: ScorerRef
    expectations: Annotated[tuple[ExpectationRef, ...], AfterValidator(ascending)] = (
        Field(min_length=1)
    )
    engines: tuple[JudgeEngine, ...] = ()

    def engine_of(self, judge: str) -> str:
        for e in self.engines:
            if e.judge == judge:
                return e.engine
        raise StructuralError(f"the scoring pins no engine for judge {judge}")

    @override
    def cross_check(self, get: Resolver) -> list[str]:
        scorer = resolve(get, self.scorer, Scorer)
        pinned = [e.judge for e in self.engines]
        if sorted(pinned) != sorted(scorer.judges):
            return ["the scoring pins an engine for other judges than its scorer's"]
        problems = [
            f"engine {e.engine} serves other weights than judge {e.judge}'s"
            for e in self.engines
            if model_of(e.engine, get).digest != resolve(get, e.judge, Judge).model
        ]
        cases: set[str] = set()
        for ref in self.expectations:
            e = resolve(get, ref, Expectation)
            if e.expectation_schema != scorer.expectation_schema:
                problems.append(f"expectation {ref} is not in the scorer's schema")
            if e.case in cases:
                problems.append(f"case {e.case} has more than one expectation")
            cases.add(e.case)
        return problems


ScoringRef = Annotated[Digest, RefTo("scoring")]
