from typing import Annotated, Any, ClassVar, cast

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Discriminator,
    Field,
    JsonValue,
    StringConstraints,
    Tag,
    model_validator,
)

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.coercion.pydantic import Mode
from chatddx.repo.entities.reasoning.pydantic import (
    INTENTS,
    REASONING_WRITES,
    Effort,
    Intent,
)
from chatddx.repo.entities.sampling.pydantic import SamplingValues
from chatddx.repo.entities.serving.pydantic import Requirement
from chatddx.repo.families import (
    BaseBranch,
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchDetails,
    BranchDetailsPatch,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
    TrailRef,
)
from chatddx.repo.families.fields import STORE_PATH, PinnedSource


def _snapshot(value: str) -> str:
    if value.startswith("/"):
        if not STORE_PATH.fullmatch(value):
            raise ValueError(
                f"{value!r}: a local LLM is the store path of the derivation "
                + "that fetched it (/nix/store/<hash>-<name>)"
            )
    elif "/" in value:
        raise ValueError(
            f"{value!r} names a repository, not a snapshot: fetch it as a "
            + "fixed-output derivation and give its store path, or give a "
            + "cloud provider's dated model name"
        )

    return value


class Refusal(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    refused: Annotated[str, StringConstraints(min_length=1)]


def _refusal_or(other: str):
    def kind(value: Any) -> str:
        match value:
            case Refusal() | {"refused": _}:
                return "refusal"
            case _:
                return other

    return kind


def _within_reasoning(fragment: dict[str, JsonValue]) -> dict[str, JsonValue]:
    outside = sorted(set(fragment) - REASONING_WRITES)

    if outside:
        raise ValueError(
            f"reasoning writes {sorted(REASONING_WRITES)}, and nothing else: "
            + f"not {outside}"
        )

    return fragment


def _fact_kind(value: Any) -> str:
    match value:
        case str():
            return "collapse"
        case _:
            return _refusal_or("fragment")(value)


ReasoningFragment = Annotated[dict[str, JsonValue], AfterValidator(_within_reasoning)]

ReasoningFact = Annotated[
    Annotated[Intent, Tag("collapse")]
    | Annotated[Refusal, Tag("refusal")]
    | Annotated[ReasoningFragment, Tag("fragment")],
    Discriminator(_fact_kind),
]

Needs = Annotated[
    list[Requirement],
    BeforeValidator(lambda value: [value] if isinstance(value, str) else value),
]


class BudgetFact(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    field: str
    needs: Needs = Field(default_factory=list)

    @model_validator(mode="after")
    def _a_reasoning_field(self):
        _ = _within_reasoning({self.field: None})
        return self


class ReasoningFacts(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    default: Intent | None = None

    off: ReasoningFact | None = None
    on: ReasoningFact | None = None
    minimal: ReasoningFact | None = None
    low: ReasoningFact | None = None
    medium: ReasoningFact | None = None
    high: ReasoningFact | None = None
    xhigh: ReasoningFact | None = None

    budget: (
        Annotated[
            Annotated[BudgetFact, Tag("budget")] | Annotated[Refusal, Tag("refusal")],
            Discriminator(_refusal_or("budget")),
        ]
        | None
    ) = None

    def resolve(
        self, effort: Effort
    ) -> tuple[Intent, dict[str, JsonValue] | Refusal] | None:
        path: list[Intent] = []
        intent: Intent | None = self.default if effort == "default" else effort

        while intent is not None:
            if intent in path:
                raise ValueError(
                    f"{' -> '.join([*path, intent])}: the collapses go round"
                )

            path.append(intent)
            fact = getattr(self, intent)

            match fact:
                case None:
                    return None
                case str():
                    intent = cast(Intent, fact)
                case _:
                    return intent, fact

        return None

    def realized(self) -> frozenset[Intent]:
        return frozenset(
            intent for intent in INTENTS if isinstance(getattr(self, intent), dict)
        )

    @model_validator(mode="after")
    def _every_collapse_lands(self):
        for effort in ("default", *INTENTS):
            fact = self.default if effort == "default" else getattr(self, effort)

            if isinstance(fact, str) and self.resolve(effort) is None:
                raise ValueError(
                    f"'{effort}' collapses into '{fact}', which ends in no fact"
                )

        return self


class SamplingFacts(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    recommended: dict[Intent, SamplingValues] = Field(default_factory=dict)
    generation_config: SamplingValues | None = None


class ModeFact(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    needs: Needs = Field(default_factory=list)
    note: str | None = None


CoercionFact = Annotated[
    Annotated[ModeFact, Tag("mode")] | Annotated[Refusal, Tag("refusal")],
    Discriminator(_refusal_or("mode")),
]


class CoercionFacts(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    default: Mode | None = None

    native: CoercionFact | None = None
    tool: CoercionFact | None = None
    prompted: CoercionFact | None = None

    @model_validator(mode="after")
    def _auto_resolves_to_a_mode_that_works(self):
        if self.default is not None and not isinstance(
            getattr(self, self.default), ModeFact
        ):
            raise ValueError(
                f"`auto` resolves to '{self.default}', which the facts don't "
                + "say works"
            )

        return self


class LLMFacts(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    reasoning: ReasoningFacts = Field(default_factory=ReasoningFacts)
    sampling: SamplingFacts = Field(default_factory=SamplingFacts)
    coercion: CoercionFacts = Field(default_factory=CoercionFacts)
    profile: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _recommended_for_modes_there_are(self):
        modes = self.reasoning.realized()
        strays = sorted(set(self.sampling.recommended) - modes)

        if strays:
            raise ValueError(
                f"sampling is recommended for {strays}, which the reasoning "
                + f"facts don't resolve to; the modes are {sorted(modes)}"
            )

        return self


class LLMSpecs(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    family: str | None = None
    parameters_b: float | None = Field(default=None, gt=0)
    active_parameters_b: float | None = Field(default=None, gt=0)
    quantization: str | None = None
    context_length: int | None = Field(default=None, gt=0)
    licence: str | None = None


class LLMDetails(Details):
    source: PinnedSource | None = None
    specs: LLMSpecs | None = None
    facts: LLMFacts = Field(default_factory=LLMFacts)


class LLMTrailBase(BaseTrail):
    snapshot: Annotated[str, AfterValidator(_snapshot)]


class LLMTrailIn(LLMTrailBase, TrailIn):
    pass


class LLMTrailRef(TrailRef, LLMTrailBase):
    pass


class LLMTrailOut(LLMTrailBase, TrailOut):
    pass


class LLMBranchDetails(BranchDetails, LLMDetails):
    pass


class LLMBranchDetailsPatch(BranchDetailsPatch, LLMDetails):
    pass


class LLMBranchIn(BaseBranch[LLMTrailIn], LLMBranchDetails):
    pass


class LLMBranchOut(BranchOut[LLMTrailOut, LLMDetails]):
    pass


class LLMFormDataIn(LLMTrailBase, BaseFormDataIn):
    source: PinnedSource | None = None
    specs: LLMSpecs | None = None
    facts: LLMFacts = Field(default_factory=LLMFacts)


class LLMFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    snapshot: str
    source: str | None
    specs: LLMSpecs | None
    facts: LLMFacts
