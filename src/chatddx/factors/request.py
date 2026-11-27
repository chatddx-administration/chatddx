import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from difflib import SequenceMatcher
from typing import Annotated, ClassVar, Literal, NamedTuple, cast, override
from urllib.parse import unquote

from pydantic import (
    AfterValidator,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

from .base import (
    Api,
    Code,
    Component,
    Digest,
    Frozen,
    Invalid,
    Language,
    RefTo,
    Resolver,
    Settings,
    StructuralError,
    display_names,
    distinct,
    resolve,
    sorted_keys,
)
from .engine import ModelRef, model_of
from .facts import (
    Effort,
    FactsRef,
    Landing,
    ModelFacts,
    Refused,
    SamplingValues,
    Writes,
)
from .response import message, tool_calls

SlotName = Literal["vignette", "appendices", "completion", "expectation"]
InsertName = Literal["schema", "output_guidance", "tool_guidance"]
# Policy: as with CleanupOp (cases.py), each op name pins one behavior; a changed
# behavior gets a new name.
SchemaOp = Literal["inline_refs@1"]
Purpose = Literal["generation", "judge"]

SLOTS_BY_PURPOSE: dict[Purpose, frozenset[SlotName]] = {
    "generation": frozenset({"vignette", "appendices"}),
    "judge": frozenset({"vignette", "appendices", "completion", "expectation"}),
}
_REQUIRED_SLOTS: dict[Purpose, frozenset[SlotName]] = {
    "generation": frozenset({"vignette"}),
    "judge": frozenset({"completion"}),
}
INSERTS_BY_KIND: dict[str, frozenset[InsertName]] = {
    "chunk.instructions": frozenset({"output_guidance", "tool_guidance"}),
    "chunk.prompt": frozenset({"output_guidance", "tool_guidance"}),
    "chunk.output": frozenset({"schema"}),
}

RUNTIME_KEYS = frozenset(
    {"model", "messages", "seed", "stream", "n", "return_token_ids"}
)
OUTPUT_KEYS = frozenset({"response_format", "tools", "tool_choice"})
MANAGED_KEYS = frozenset(
    {
        "temperature",
        "top_p",
        "top_k",
        "min_p",
        "presence_penalty",
        "frequency_penalty",
        "repetition_penalty",
        "stop",
        "max_completion_tokens",
        "max_tokens",
        "reasoning_effort",
        "thinking_token_budget",
        "chat_template_kwargs",
    }
)
# Policy: vLLM request keys that would replace the engine's chat template, constrain the
# answer outside the output contract, or put the prompt's text in the stored response.
BYPASS_KEYS = frozenset(
    {"chat_template", "structured_outputs", "return_prompt_text", "prompt_logprobs"}
)
_GREEDY_DROPS = ("top_p", "top_k", "min_p")


class Slot(Frozen):
    slot: SlotName


Segment = str | Slot


class Insert(Frozen):
    insert: InsertName
    before: str = ""
    after: str = ""


def _merged[T](segments: Iterable[str | T]) -> tuple[str | T, ...]:
    merged: list[str | T] = []
    for s in segments:
        if isinstance(s, str) and merged and isinstance(merged[-1], str):
            merged[-1] += s
        else:
            merged.append(s)
    return tuple(s for s in merged if s != "")


def _text(text: str | tuple[str | Insert, ...]) -> str | tuple[str | Insert, ...]:
    if isinstance(text, str):
        return text
    merged = _merged(text)
    if all(isinstance(s, str) for s in merged):
        return "".join(cast(tuple[str, ...], merged))
    return merged


Text = Annotated[str | tuple[str | Insert, ...], AfterValidator(_text)]


def _segments(text: str | tuple[str | Insert, ...]) -> tuple[str | Insert, ...]:
    return (text,) if isinstance(text, str) else text


def _inserts(segments: Iterable[object]) -> list[InsertName]:
    return [s.insert for s in segments if isinstance(s, Insert)]


def _check_inserts(kind: str, segments: Iterable[object]) -> list[InsertName]:
    used = _inserts(segments)
    if stray := set(used) - INSERTS_BY_KIND[kind]:
        inserts = display_names(stray)
        raise Invalid.of(
            "%(kind)s cannot use inserts %(inserts)s", kind=kind, inserts=inserts
        )
    if dupes := {i for i in used if used.count(i) > 1}:
        inserts = display_names(dupes)
        raise Invalid.of("inserts used more than once: %(inserts)s", inserts=inserts)
    return used


def _fill(
    segments: Iterable[Segment | Insert], fills: Mapping[InsertName, str]
) -> tuple[Segment, ...]:
    filled: list[Segment] = []
    for s in segments:
        if isinstance(s, Insert):
            text = fills[s.insert]
            filled.append(f"{s.before}{text}{s.after}" if text else "")
        else:
            filled.append(s)
    return _merged(filled)


def _fill_text(
    text: str | tuple[str | Insert, ...], fills: Mapping[InsertName, str]
) -> str:
    return "".join(s for s in _fill(_segments(text), fills) if isinstance(s, str))


class Message(Frozen):
    role: Literal["system", "developer", "user", "assistant"]
    content: tuple[Segment, ...] = Field(min_length=1)


def _canonical_sampling(data: object) -> object:
    if not isinstance(data, dict):
        return data
    fields = cast(dict[str, object], data)
    if fields.get("temperature") != 0:
        return fields
    return {k: v for k, v in fields.items() if k not in _GREEDY_DROPS}


class Instructions(Component):
    kind: Literal["chunk.instructions"] = "chunk.instructions"
    role: Literal["system", "developer"] = "system"
    text: Text

    @model_validator(mode="after")
    def _inserts(self) -> "Instructions":
        _ = _check_inserts(self.kind, _segments(self.text))
        return self


class Example(Frozen):
    role: Literal["user", "assistant"]
    content: str


class FewShot(Component):
    kind: Literal["chunk.few_shot"] = "chunk.few_shot"
    messages: tuple[Example, ...] = Field(min_length=1)


class Prompt(Component):
    kind: Literal["chunk.prompt"] = "chunk.prompt"
    purpose: Purpose = "generation"
    segments: tuple[Segment | Insert, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _slots(self) -> "Prompt":
        _check_slots(self.purpose, [self.segments])
        _ = _check_inserts(self.kind, self.segments)
        return self


class NativeOutput(Frozen):
    kind: Literal["native"] = "native"


class ToolOutput(Frozen):
    kind: Literal["tool"] = "tool"
    name: str
    description: str | None = Field(default=None, min_length=1)


class TextOutput(Frozen):
    kind: Literal["text"] = "text"


OutputContract = Annotated[
    NativeOutput | ToolOutput | TextOutput, Field(discriminator="kind")
]


class CompiledText(Frozen):
    kind: Literal["text"] = "text"
    json_schema: dict[str, JsonValue] | None = None


CompiledContract = Annotated[
    NativeOutput | ToolOutput | CompiledText, Field(discriminator="kind")
]


def _pointer(schema: dict[str, JsonValue], ref: str) -> JsonValue:
    if ref != "#" and not ref.startswith("#/"):
        raise Invalid.of("%(ref)s is outside the schema", ref=ref)
    node: JsonValue = schema
    for token in unquote(ref[2:]).split("/") if ref != "#" else ():
        key = token.replace("~1", "/").replace("~0", "~")
        match node:
            case dict() if key in node:
                node = node[key]
            case list() if key.isdigit() and int(key) < len(node):
                node = node[int(key)]
            case _:
                raise Invalid.of("%(ref)s refers to nothing", ref=ref)
    return node


def _inline_refs(schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    def resolve(node: JsonValue, seen: tuple[str, ...]) -> JsonValue:
        match node:
            case {"$ref": str(ref), **siblings}:
                if ref in seen:
                    raise Invalid.of("%(ref)s refers to itself", ref=ref)
                target = resolve(_pointer(schema, ref), (*seen, ref))
                rest = {k: resolve(v, seen) for k, v in siblings.items()}
                return {**target, **rest} if isinstance(target, dict) else target
            case dict():
                return {k: resolve(v, seen) for k, v in node.items()}
            case list():
                return [resolve(v, seen) for v in node]
            case _:
                return node

    top = {k: v for k, v in schema.items() if k not in ("$defs", "definitions")}
    return cast(dict[str, JsonValue], resolve(top, ()))


_SCHEMA_OPS: dict[SchemaOp, Callable[[dict[str, JsonValue]], dict[str, JsonValue]]] = {
    "inline_refs@1": _inline_refs,
}


class Output(Component):
    kind: Literal["chunk.output"] = "chunk.output"
    contract: OutputContract
    json_schema: dict[str, JsonValue] | None = None
    guidance: Text | None = None
    schema_ops: Annotated[tuple[SchemaOp, ...], AfterValidator(distinct)] = ()

    @model_validator(mode="after")
    def _schema_placement(self) -> "Output":
        if not isinstance(self.contract, TextOutput) and self.json_schema is None:
            raise Invalid.of(
                "%(contract)s contracts need json_schema", contract=self.contract.kind
            )
        return self

    @model_validator(mode="after")
    def _inserts(self) -> "Output":
        if self.guidance is None:
            return self
        used = _check_inserts(self.kind, _segments(self.guidance))
        if "schema" in used and self.output_schema is None:
            raise Invalid.of("only an output with a schema can show it")
        return self

    @model_validator(mode="after")
    def _schema_ops(self) -> "Output":
        if self.schema_ops and self.json_schema is None:
            raise Invalid.of("schema ops need a schema")
        _ = self.output_schema
        return self

    @property
    def output_schema(self) -> dict[str, JsonValue] | None:
        schema = self.json_schema
        if schema is None:
            return None
        for op in self.schema_ops:
            schema = _SCHEMA_OPS[op](schema)
        return schema

    def guidance_text(self) -> str:
        if self.guidance is None:
            return ""
        schema = json.dumps(self.output_schema, indent=2, ensure_ascii=False)
        return _fill_text(self.guidance, {"schema": schema})


class Sampling(Component):
    kind: Literal["chunk.sampling"] = "chunk.sampling"
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    repetition_penalty: float | None = None
    stop: tuple[str, ...] = ()
    max_output_tokens: int | None = Field(default=None, ge=1)
    max_tokens_key: Literal["max_completion_tokens", "max_tokens"] = (
        "max_completion_tokens"
    )
    recommended: bool = False

    @model_validator(mode="before")
    @classmethod
    def _greedy(cls, data: object) -> object:
        return _canonical_sampling(data)

    def over(self, values: SamplingValues) -> "Sampling":
        own = self.model_dump(exclude={"kind", "recommended"}, exclude_none=True)
        return Sampling.model_validate({**values.model_dump(exclude_none=True), **own})

    def body(self) -> dict[str, JsonValue]:
        body: dict[str, JsonValue] = self.model_dump(
            exclude_none=True,
            exclude={
                "kind",
                "stop",
                "max_output_tokens",
                "max_tokens_key",
                "recommended",
            },
        )
        if self.stop:
            body["stop"] = list(self.stop)
        if self.max_output_tokens is not None:
            body[self.max_tokens_key] = self.max_output_tokens
        return body


class Reasoning(Component):
    kind: Literal["chunk.reasoning"] = "chunk.reasoning"
    effort: Literal["none", "minimal", "low", "medium", "high"] | None = None
    thinking_token_budget: int | None = Field(default=None, ge=0)
    chat_template_kwargs: Settings = Field(default_factory=dict)
    level: Effort | None = None

    @model_validator(mode="after")
    def _level_or_settings(self) -> "Reasoning":
        if self.level is not None and (
            self.effort is not None or self.chat_template_kwargs
        ):
            raise Invalid.of(
                "a reasoning level is worked out from the model's facts, so it comes "
                + "without an effort or chat template arguments"
            )
        return self


class Passthrough(Component):
    kind: Literal["chunk.passthrough"] = "chunk.passthrough"
    body: Settings

    @model_validator(mode="after")
    def _no_owned_keys(self) -> "Passthrough":
        reserved = RUNTIME_KEYS | OUTPUT_KEYS | MANAGED_KEYS | BYPASS_KEYS
        if owned := self.body.keys() & reserved:
            raise Invalid.of(
                "passthrough may not set %(keys)s", keys=str(sorted(owned))
            )
        return self


ToolName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
EntryPoint = Annotated[str, StringConstraints(pattern=r"^[\w.]+:[\w.]+$")]


class Tool(Component):
    kind: Literal["tool"] = "tool"
    schema_version: ClassVar[int] = 2
    name: ToolName
    description: str = Field(min_length=1)
    parameters: dict[str, JsonValue]
    entry_point: EntryPoint
    version: int = Field(ge=1)


ToolRef = Annotated[Digest, RefTo("tool")]


class Toolset(Component):
    kind: Literal["chunk.toolset"] = "chunk.toolset"
    tools: tuple[ToolRef, ...] = Field(min_length=1)
    guidance: str | None = Field(default=None, min_length=1)
    max_rounds: int = Field(default=5, ge=1)

    @override
    def cross_check(self, get: Resolver) -> list[str]:
        names = [resolve(get, t, Tool).name for t in self.tools]
        if dupes := sorted({n for n in names if names.count(n) > 1}):
            return [f"tools named more than once: {dupes}"]
        return []


class Translations(Component):
    schema_version: ClassVar[int] = 2
    kind: Literal["chunk.translations"] = "chunk.translations"
    into: Annotated[dict[Language, dict[str, str]], AfterValidator(sorted_keys)] = (
        Field(min_length=1)
    )

    @field_validator("into")
    @classmethod
    def _into(cls, into: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        for language, entries in into.items():
            if not entries:
                raise Invalid.of("no translations into %(into)s", into=language)
            if any(not text.strip() for text in entries):
                raise Invalid.of("whitespace isn't translated")
            if empty := sorted(
                text for text, translation in entries.items() if not translation
            ):
                raise Invalid.of(
                    "no translation into %(into)s for %(texts)s",
                    into=language,
                    texts=str(empty),
                )
        return {language: sorted_keys(entries) for language, entries in into.items()}


class AppendixLayout(Frozen):
    before: str = "\n\n"
    between: str = "\n\n"
    after: str = ""

    def join(self, appendices: list[str]) -> str:
        if not appendices:
            return ""
        return self.before + self.between.join(appendices) + self.after


class Recipe(Frozen):
    purpose: Purpose = "generation"
    instructions: Annotated[Digest, RefTo("chunk.instructions")] | None = None
    few_shot: Annotated[Digest, RefTo("chunk.few_shot")] | None = None
    prompt: Annotated[Digest, RefTo("chunk.prompt")]
    output: Annotated[Digest, RefTo("chunk.output")]
    sampling: Annotated[Digest, RefTo("chunk.sampling")]
    reasoning: Annotated[Digest, RefTo("chunk.reasoning")] | None = None
    passthrough: Annotated[Digest, RefTo("chunk.passthrough")] | None = None
    appendix_layout: AppendixLayout = AppendixLayout()
    translations: Annotated[Digest, RefTo("chunk.translations")] | None = None
    toolset: Annotated[Digest, RefTo("chunk.toolset")] | None = None
    model: ModelRef


CHUNK_PARTS = (
    "instructions",
    "few_shot",
    "prompt",
    "output",
    "sampling",
    "reasoning",
    "passthrough",
    "translations",
    "toolset",
)
RECIPE_PARTS = (*CHUNK_PARTS, "model")
OPTIONAL_PARTS = tuple(
    p for p in RECIPE_PARTS if not Recipe.model_fields[p].is_required()
)


class Skeleton(Component):
    kind: Literal["skeleton"] = "skeleton"
    purpose: Purpose = "generation"
    api: Api = "chat.completions"
    messages: tuple[Message, ...] = Field(min_length=1)
    body: Settings = Field(default_factory=dict)
    contract: CompiledContract
    appendix_layout: AppendixLayout = AppendixLayout()
    tools: tuple[ToolRef, ...] = ()
    max_rounds: int | None = Field(default=None, ge=1)

    @model_validator(mode="before")
    @classmethod
    def _greedy_body(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        fields = cast(dict[str, object], data)
        if "body" not in fields:
            return fields
        return {**fields, "body": _canonical_sampling(fields["body"])}

    @model_validator(mode="after")
    def _structure(self) -> "Skeleton":
        if owned := self.body.keys() & RUNTIME_KEYS:
            raise ValueError(f"body may not set {sorted(owned)}")
        _check_slots(self.purpose, [m.content for m in self.messages])
        if bool(self.tools) != (self.max_rounds is not None):
            raise ValueError("a skeleton has max_rounds exactly when it has tools")
        keys = set(self.body) & OUTPUT_KEYS
        names = _tool_names(self.body)
        if len(set(names)) != len(names):
            raise ValueError("tools named more than once")
        choice = self.body.get("tool_choice")
        match self.contract:
            case NativeOutput() if self.tools:
                if keys != {"response_format", "tools", "tool_choice"} or (
                    choice != "auto"
                ):
                    raise ValueError(
                        "native contract with tools needs response_format, tools "
                        + "and tool_choice auto"
                    )
            case NativeOutput():
                if keys != {"response_format"}:
                    raise ValueError(
                        "native contract needs response_format and no tools"
                    )
            case ToolOutput(name=name, description=description):
                if keys != {"tools", "tool_choice"}:
                    raise ValueError("tool contract needs tools and tool_choice only")
                if self.tools and (name not in names or choice != "required"):
                    raise ValueError(
                        f"tool contract with tools needs a tool named {name!r} "
                        + "and tool_choice required"
                    )
                if not self.tools and names != [name]:
                    raise ValueError(
                        f"tool contract needs exactly one tool named {name!r}"
                    )
                if _tool_description(self.body, name) != description:
                    raise ValueError(
                        f"tool contract needs its tool described as {description!r}"
                    )
            case CompiledText() if self.tools:
                if keys != {"tools", "tool_choice"} or choice != "auto":
                    raise ValueError(
                        "text contract with tools needs tools and tool_choice auto"
                    )
            case CompiledText():
                if keys:
                    raise ValueError("text contract may not constrain the output")
        match self.contract, self.output_schema:
            case (CompiledText(), _) | (_, dict()):
                pass
            case _:
                raise ValueError(
                    f"{self.contract.kind} contract needs its schema as an object"
                )
        return self

    @override
    def cross_check(self, get: Resolver) -> list[str]:
        answer = self.contract.name if isinstance(self.contract, ToolOutput) else None
        offered = [n for n in _tool_names(self.body) if n != answer]
        named = [resolve(get, t, Tool).name for t in self.tools]
        if offered != named:
            return [f"the body offers tools {offered}, the skeleton names {named}"]
        return []

    @property
    def greedy(self) -> bool:
        return self.body.get("temperature") == 0

    @property
    def output_schema(self) -> JsonValue:
        match self.contract:
            case NativeOutput():
                match self.body.get("response_format"):
                    case {"type": "json_schema", "json_schema": {"schema": schema}}:
                        return schema
                    case _:
                        return None
            case ToolOutput(name=name):
                function = _tool_function(self.body, name)
                return None if function is None else function.get("parameters")
            case CompiledText(json_schema=schema):
                return schema

    def render(
        self,
        *,
        model: str,
        seed: int | None,
        fills: Mapping[SlotName, str],
        return_token_ids: bool = True,
    ) -> dict[str, JsonValue]:
        slots = {
            s.slot for m in self.messages for s in m.content if isinstance(s, Slot)
        }
        if missing := slots - fills.keys():
            raise StructuralError(f"no fill for slots {sorted(missing)}")
        messages: list[JsonValue] = []
        for m in self.messages:
            parts = [s if isinstance(s, str) else fills[s.slot] for s in m.content]
            messages.append({"role": m.role, "content": "".join(parts)})
        body: dict[str, JsonValue] = {"model": model, "messages": messages, **self.body}
        if seed is not None and not self.greedy:
            body["seed"] = seed
        if return_token_ids:
            body["return_token_ids"] = True
        return body


SkeletonRef = Annotated[Digest, RefTo("skeleton")]


class Compilation(Component):
    schema_version: ClassVar[int] = 3
    kind: Literal["compilation"] = "compilation"
    recipe: Recipe
    skeleton: SkeletonRef
    compiler: Code
    facts: FactsRef | None = None
    into: Language | None = None

    @override
    def cross_check(self, get: Resolver) -> list[str]:
        found: list[str] = []
        if self.facts is not None:
            facts = resolve(get, self.facts, ModelFacts)
            if (model := model_of(self.recipe.model, get).name) != facts.model:
                found.append(f"facts about {facts.model} compiled a recipe for {model}")
        if self.into is not None and self.into not in translated(self.recipe, get):
            found.append(f"the recipe has no translations into {self.into}")
        return found


def _tool_name(tool: JsonValue) -> str:
    match tool:
        case {"function": {"name": str() as name}}:
            return name
        case _:
            raise Invalid.of(
                "a tool needs a function with a name, not %(tool)s", tool=repr(tool)
            )


def _tool_names(body: Mapping[str, JsonValue]) -> list[str]:
    match body.get("tools"):
        case None:
            return []
        case list() as tools:
            return [_tool_name(t) for t in tools]
        case _:
            raise Invalid.of("tools must be a list")


def _tool_function(
    body: Mapping[str, JsonValue], name: str
) -> dict[str, JsonValue] | None:
    tools = body.get("tools")
    for t in tools if isinstance(tools, list) else []:
        match t:
            case {"function": {"name": str() as n} as function} if n == name:
                return function
            case _:
                pass
    return None


def _tool_description(body: Mapping[str, JsonValue], name: str) -> JsonValue:
    function = _tool_function(body, name)
    return None if function is None else function.get("description")


def _check_slots(
    purpose: Purpose, contents: Sequence[tuple[Segment | Insert, ...]]
) -> None:
    used = [s.slot for c in contents for s in c if isinstance(s, Slot)]
    if stray := set(used) - SLOTS_BY_PURPOSE[purpose]:
        slots = display_names(stray)
        raise Invalid.of(
            "%(purpose)s requests cannot use slots %(slots)s",
            purpose=purpose,
            slots=slots,
        )
    if missing := _REQUIRED_SLOTS[purpose] - set(used):
        slots = display_names(missing)
        raise Invalid.of(
            "%(purpose)s requests need slots %(slots)s", purpose=purpose, slots=slots
        )
    if dupes := {s for s in used if used.count(s) > 1}:
        slots = display_names(dupes)
        raise Invalid.of("slots used more than once: %(slots)s", slots=slots)


_Translate = Callable[[str], str]

_PROSE = frozenset({"title", "description"})
_NAMED = frozenset(
    {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"}
)
_DATA = frozenset({"enum", "const", "default", "examples"})


def _tr(text: str, tr: _Translate) -> str:
    return tr(text) if text.strip() else text


def _tr_segments[T](
    segments: Iterable[str | Insert | T], tr: _Translate
) -> tuple[str | Insert | T, ...]:
    translated: list[str | Insert | T] = []
    for s in segments:
        if isinstance(s, str):
            translated.append(_tr(s, tr))
        elif isinstance(s, Insert):
            translated.append(
                Insert(
                    insert=s.insert, before=_tr(s.before, tr), after=_tr(s.after, tr)
                )
            )
        else:
            translated.append(s)
    return tuple(translated)


def _tr_text(
    text: str | tuple[str | Insert, ...], tr: _Translate
) -> str | tuple[str | Insert, ...]:
    return _tr(text, tr) if isinstance(text, str) else _tr_segments(text, tr)


def _tr_schema(node: JsonValue, tr: _Translate) -> JsonValue:
    match node:
        case list():
            return [_tr_schema(v, tr) for v in node]
        case dict():
            translated: dict[str, JsonValue] = {}
            for k, v in node.items():
                if k in _PROSE and isinstance(v, str):
                    translated[k] = _tr(v, tr)
                elif k in _NAMED and isinstance(v, dict):
                    translated[k] = {name: _tr_schema(s, tr) for name, s in v.items()}
                elif k in _DATA:
                    translated[k] = v
                else:
                    translated[k] = _tr_schema(v, tr)
            return translated
        case _:
            return node


def _tr_layout(layout: AppendixLayout, tr: _Translate) -> AppendixLayout:
    return AppendixLayout(
        before=_tr(layout.before, tr),
        between=_tr(layout.between, tr),
        after=_tr(layout.after, tr),
    )


def _tr_output(output: Output, tr: _Translate) -> Output:
    doc = output.model_dump()
    if output.guidance is not None:
        doc["guidance"] = _tr_text(output.guidance, tr)
    if output.json_schema is not None:
        doc["json_schema"] = _tr_schema(output.json_schema, tr)
    match output.contract:
        case ToolOutput(description=str() as description):
            doc["contract"] = {**doc["contract"], "description": _tr(description, tr)}
        case _:
            pass
    return Output.model_validate(doc)


class _Parts(NamedTuple):
    instructions: Instructions | None
    few_shot: FewShot | None
    prompt: Prompt
    output: Output
    appendix_layout: AppendixLayout
    toolset: Toolset | None
    tools: tuple[Tool, ...]


def _tr_instructions(c: Instructions, tr: _Translate) -> Instructions:
    return Instructions(role=c.role, text=_tr_text(c.text, tr))


def _tr_few_shot(f: FewShot, tr: _Translate) -> FewShot:
    return FewShot(
        messages=tuple(
            Example(role=m.role, content=_tr(m.content, tr)) for m in f.messages
        )
    )


def _tr_prompt(p: Prompt, tr: _Translate) -> Prompt:
    return Prompt(purpose=p.purpose, segments=_tr_segments(p.segments, tr))


def _tr_toolset(
    ts: Toolset, get: Resolver, tr: _Translate
) -> tuple[Toolset, tuple[Tool, ...]]:
    toolset = Toolset(
        tools=ts.tools,
        guidance=None if ts.guidance is None else _tr(ts.guidance, tr),
        max_rounds=ts.max_rounds,
    )
    tools = tuple(
        Tool.model_validate(
            {
                **tool.model_dump(),
                "description": _tr(tool.description, tr),
                "parameters": _tr_schema(tool.parameters, tr),
            }
        )
        for tool in (resolve(get, d, Tool) for d in ts.tools)
    )
    return toolset, tools


def _parts(recipe: Recipe, get: Resolver, tr: _Translate) -> _Parts:
    instructions = few_shot = None
    if recipe.instructions is not None:
        c = resolve(get, recipe.instructions, Instructions)
        instructions = _tr_instructions(c, tr)
    if recipe.few_shot is not None:
        few_shot = _tr_few_shot(resolve(get, recipe.few_shot, FewShot), tr)
    prompt = _tr_prompt(resolve(get, recipe.prompt, Prompt), tr)
    output = _tr_output(resolve(get, recipe.output, Output), tr)
    appendix_layout = _tr_layout(recipe.appendix_layout, tr)
    toolset, tools = None, ()
    if recipe.toolset is not None:
        ts = resolve(get, recipe.toolset, Toolset)
        toolset, tools = _tr_toolset(ts, get, tr)
    return _Parts(
        instructions, few_shot, prompt, output, appendix_layout, toolset, tools
    )


def texts(recipe: Recipe, get: Resolver) -> dict[str, tuple[str, ...]]:
    found: dict[str, tuple[str, ...]] = {}
    for part in ("instructions", "few_shot", "prompt", "output"):
        if (digest := getattr(recipe, part)) and (held := own_texts(get(digest), get)):
            found[part] = held
    if held := own_texts(recipe.appendix_layout, get):
        found["appendix_layout"] = held
    if recipe.toolset and (held := own_texts(get(recipe.toolset), get)):
        found["toolset"] = held
    return found


def own_texts(chunk: Component | AppendixLayout, get: Resolver) -> tuple[str, ...]:
    seen: list[str] = []

    def tr(text: str) -> str:
        if text not in seen:
            seen.append(text)
        return text

    match chunk:
        case Instructions():
            _ = _tr_instructions(chunk, tr)
        case FewShot():
            _ = _tr_few_shot(chunk, tr)
        case Prompt():
            _ = _tr_prompt(chunk, tr)
        case Output():
            _ = _tr_output(chunk, tr)
        case Toolset():
            _ = _tr_toolset(chunk, get, tr)
        case AppendixLayout():
            _ = _tr_layout(chunk, tr)
        case _:
            pass
    return tuple(seen)


def translated(recipe: Recipe, get: Resolver) -> dict[str, dict[str, str]]:
    if recipe.translations is None:
        return {}
    return resolve(get, recipe.translations, Translations).into


def untranslated(recipe: Recipe, get: Resolver, into: str) -> tuple[str, ...]:
    entries = translated(recipe, get).get(into, {})
    held = {t for found in texts(recipe, get).values() for t in found}
    return tuple(sorted(held - entries.keys()))


def remapped(
    before: Mapping[str, tuple[str, ...]],
    after: Mapping[str, tuple[str, ...]],
    into: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, str]]:
    """Moves each translation of a text that changed in place, matched part by part
    and in order, over to the text it changed into, dropping the old key once no part
    holds it; every other translation is kept."""
    moved: dict[str, str] = {}
    for part, now in after.items():
        was = before.get(part, ())
        matched = SequenceMatcher(a=was, b=now, autojunk=False)
        for op, i1, i2, j1, j2 in matched.get_opcodes():
            if op == "replace":
                for old, new in zip(was[i1:i2], now[j1:j2], strict=False):
                    _ = moved.setdefault(new, old)
    held = {t for found in after.values() for t in found}
    left = {old for old in moved.values() if old not in held}
    found: dict[str, dict[str, str]] = {}
    for language, entries in into.items():
        kept = {k: v for k, v in entries.items() if k not in left}
        for new, old in moved.items():
            if new not in kept and old in entries:
                kept[new] = entries[old]
        if kept:
            found[language] = dict(sorted(kept.items()))
    return found


def landings(
    recipe: Recipe, get: Resolver, facts: ModelFacts | None
) -> tuple[Landing | None, Landing | None]:
    if facts is not None and (model := model_of(recipe.model, get).name) != facts.model:
        raise StructuralError.raw(
            "facts about %(facts)s can't compile for %(model)s",
            facts=facts.model,
            model=model,
        )
    reasoning = (
        None if recipe.reasoning is None else resolve(get, recipe.reasoning, Reasoning)
    )
    sampling = resolve(get, recipe.sampling, Sampling)
    asked = None if reasoning is None else reasoning.level
    if asked is None and not sampling.recommended:
        return None, None
    if facts is None:
        if asked is None:
            raise StructuralError.of(
                "a recommended sampling is worked out from the facts about the "
                + "recipe's model, which has none"
            )
        raise StructuralError.of(
            "reasoning %(level)s is worked out from the facts about the recipe's "
            + "model, which has none",
            level=repr(asked),
        )
    try:
        landed = None if asked is None else facts.reasoning.landing(asked)
        if landed is not None and reasoning and reasoning.thinking_token_budget:
            facts.check_budget()
        followed = None
        if sampling.recommended:
            followed = landed or facts.reasoning.landing("default")
            _ = facts.recommended(followed.level)
    except Refused as e:
        raise StructuralError.of(
            "%(model)s: %(refused)s", model=facts.model, refused=str(e)
        ) from None
    return landed, followed


Origin = Literal[
    "instructions",
    "few_shot",
    "prompt",
    "output_guidance",
    "output_schema",
    "tool_guidance",
    "appendix_layout",
    "joining",
]


class Run(Frozen):
    text: str
    origin: Origin
    untranslated: bool = False


class TracedMessage(Frozen):
    role: Literal["system", "developer", "user", "assistant"]
    runs: tuple[Run | Slot, ...]


class Traced(NamedTuple):
    skeleton: Skeleton
    messages: tuple[TracedMessage, ...]
    appendix_layout: tuple[Run, Run, Run]


class _Tracer(NamedTuple):
    entries: Mapping[str, str] | None

    def tr(self, text: str) -> str:
        return text if self.entries is None else self.entries.get(text, text)

    def missing(self, text: str) -> bool:
        return (
            self.entries is not None and bool(text.strip()) and text not in self.entries
        )

    def run(self, text: str, origin: Origin) -> Run:
        return Run(
            text=_tr(text, self.tr), origin=origin, untranslated=self.missing(text)
        )

    def said(self, text: str, origin: Origin) -> list[Run]:
        run = self.run(text, origin)
        return [run] if run.text else []

    def segments(
        self,
        segments: Iterable[Segment | Insert],
        origin: Origin,
        fills: Mapping[InsertName, Sequence[Run]],
    ) -> list[Run | Slot]:
        runs: list[Run | Slot] = []
        for s in segments:
            match s:
                case str():
                    runs += self.said(s, origin)
                case Slot():
                    runs.append(s)
                case Insert(insert=name, before=before, after=after):
                    if filled := fills[name]:
                        runs += [
                            *self.said(before, origin),
                            *filled,
                            *self.said(after, origin),
                        ]
        return runs


def _joined(runs: Iterable[Run | Slot]) -> str:
    return "".join(r.text for r in runs if isinstance(r, Run))


def _content(runs: Iterable[Run | Slot]) -> tuple[Segment, ...]:
    return _merged(r.text if isinstance(r, Run) else r for r in runs)


def compile_request(
    recipe: Recipe,
    get: Resolver,
    facts: ModelFacts | None = None,
    into: str | None = None,
) -> Skeleton:
    return traced(recipe, get, facts, into).skeleton


def traced(
    recipe: Recipe,
    get: Resolver,
    facts: ModelFacts | None = None,
    into: str | None = None,
    *,
    partly: bool = False,
) -> Traced:
    """The request a recipe compiles to, with each message as the runs of text it is
    made of, marked with the part each came from, and the appendix layout's runs.
    `partly` compiles into a language whose translations are missing some texts, the
    texts as they are in their place, marked untranslated: its skeleton is no
    recipe's to run. Resolves the recipe's chunks and tools."""
    landed, followed = landings(recipe, get, facts)
    entries: dict[str, str] | None = None
    if into is not None:
        held = translated(recipe, get)
        if into not in held and not partly:
            raise StructuralError.of("no translations into %(into)s", into=into)
        if not partly and (missing := untranslated(recipe, get, into)):
            listed = ", ".join(repr(t) for t in missing)
            raise StructuralError.of(
                "no translation into %(into)s for %(texts)s", into=into, texts=listed
            )
        entries = held.get(into, {})
    tracer = _Tracer(entries)
    parts = _parts(recipe, get, tracer.tr)
    source = _parts(recipe, get, lambda text: text)
    prompt, output = parts.prompt, parts.output
    sampling = resolve(get, recipe.sampling, Sampling)
    if prompt.purpose != recipe.purpose:
        raise StructuralError.of(
            "%(prompt)s prompt in a %(recipe)s recipe",
            prompt=prompt.purpose,
            recipe=recipe.purpose,
        )

    toolset = parts.toolset
    schema: list[Run] = []
    if (shown := output.output_schema) is not None:
        prose: list[str] = []

        def kept(text: str) -> str:
            prose.append(text)
            return text

        _ = _tr_schema(source.output.json_schema, kept)
        schema = [
            Run(
                text=json.dumps(shown, indent=2, ensure_ascii=False),
                origin="output_schema",
                untranslated=any(tracer.missing(t) for t in prose),
            )
        ]
    guidance = source.output.guidance
    fills: dict[InsertName, list[Run]] = {
        "output_guidance": []
        if guidance is None
        else [
            r
            for r in tracer.segments(
                _segments(guidance), "output_guidance", {"schema": schema}
            )
            if isinstance(r, Run)
        ],
        "tool_guidance": []
        if source.toolset is None or source.toolset.guidance is None
        else tracer.said(source.toolset.guidance, "tool_guidance"),
    }
    instructions = source.instructions
    in_prompt = set(_inserts(prompt.segments))
    in_instructions = set(
        [] if instructions is None else _inserts(_segments(instructions.text))
    )
    system: list[Run | Slot] = []
    role: Literal["system", "developer"] = "system"
    if instructions is not None:
        system = tracer.segments(_segments(instructions.text), "instructions", fills)
        role = instructions.role
    # Policy: guidance goes where it's inserted, or else after the instructions, in this
    # order.
    guidances: tuple[InsertName, ...] = ("output_guidance", "tool_guidance")
    for name in guidances:
        if name in in_prompt and name in in_instructions:
            raise StructuralError.of(
                "%(insert)s is inserted in both the instructions and the prompt",
                insert=name.replace("_", " "),
            )
        if _joined(text := fills[name]) and name not in in_prompt | in_instructions:
            if _joined(system):
                system = [*system, Run(text="\n\n", origin="joining"), *text]
            else:
                system = list(text)

    messages: list[Message] = []
    runs: list[TracedMessage] = []
    if _joined(system):
        messages.append(Message(role=role, content=(_joined(system),)))
        runs.append(TracedMessage(role=role, runs=tuple(system)))
    if (few_shot := parts.few_shot) is not None and source.few_shot is not None:
        for m, was in zip(few_shot.messages, source.few_shot.messages, strict=True):
            messages.append(Message(role=m.role, content=(m.content,)))
            said = tracer.said(was.content, "few_shot")
            runs.append(TracedMessage(role=m.role, runs=tuple(said)))
    asked = tracer.segments(source.prompt.segments, "prompt", fills)
    messages.append(Message(role="user", content=_content(asked)))
    runs.append(TracedMessage(role="user", runs=tuple(asked)))

    body: dict[str, JsonValue] = {}
    if recipe.passthrough is not None:
        passthrough = resolve(get, recipe.passthrough, Passthrough)
        body.update(passthrough.body)
    if facts is not None and followed is not None:
        sampling = sampling.over(facts.recommended(followed.level))
    managed = sampling.body()
    if recipe.reasoning is not None:
        reasoning = resolve(get, recipe.reasoning, Reasoning)
        asked = Writes(
            effort=reasoning.effort,
            chat_template_kwargs=reasoning.chat_template_kwargs,
        )
        writes = asked if landed is None else landed.writes
        if writes.effort is not None:
            managed["reasoning_effort"] = writes.effort
        if reasoning.thinking_token_budget is not None:
            managed["thinking_token_budget"] = reasoning.thinking_token_budget
        if writes.chat_template_kwargs:
            managed["chat_template_kwargs"] = writes.chat_template_kwargs
    offered: list[JsonValue] = [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in parts.tools
    ]
    if offered:
        managed["tools"], managed["tool_choice"] = offered, "auto"
    compiled: NativeOutput | ToolOutput | CompiledText
    match output.contract:
        case NativeOutput() as compiled:
            managed["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "output",
                    "strict": True,
                    "schema": output.output_schema,
                },
            }
        case ToolOutput(name=name, description=description) as compiled:
            if name in {t.name for t in parts.tools}:
                raise StructuralError.of(
                    "the answer tool %(tool)s has the name of a tool in the toolset",
                    tool=repr(name),
                )
            function: dict[str, JsonValue] = {"name": name}
            if description is not None:
                function["description"] = description
            function["parameters"] = output.output_schema
            managed["tools"] = [*offered, {"type": "function", "function": function}]
            managed["tool_choice"] = (
                "required"
                if offered
                else {"type": "function", "function": {"name": name}}
            )
        case TextOutput():
            compiled = CompiledText(json_schema=output.output_schema)
    body.update(managed)

    skeleton = Skeleton(
        purpose=recipe.purpose,
        messages=tuple(messages),
        body=body,
        contract=compiled,
        appendix_layout=parts.appendix_layout,
        tools=() if toolset is None else toolset.tools,
        max_rounds=None if toolset is None else toolset.max_rounds,
    )
    layout = source.appendix_layout
    return Traced(
        skeleton,
        tuple(runs),
        (
            tracer.run(layout.before, "appendix_layout"),
            tracer.run(layout.between, "appendix_layout"),
            tracer.run(layout.after, "appendix_layout"),
        ),
    )


def compiled(
    recipe: Recipe,
    get: Resolver,
    compiler: Code,
    facts: ModelFacts | None = None,
    into: str | None = None,
) -> tuple[Skeleton, Compilation]:
    skeleton = compile_request(recipe, get, facts, into)
    worked_out = any(landings(recipe, get, facts))
    record = Compilation(
        recipe=recipe,
        skeleton=skeleton.digest,
        compiler=compiler,
        facts=facts.digest if facts is not None and worked_out else None,
        into=into,
    )
    return skeleton, record


def next_request(
    body: Mapping[str, JsonValue],
    response: Mapping[str, JsonValue],
    results: Mapping[str, str],
) -> dict[str, JsonValue]:
    said, calls = message(response), tool_calls(response)
    if missing := [c.id for c in calls if c.id not in results]:
        raise StructuralError(f"no result for tool calls {missing}")
    previous = body.get("messages")
    messages: list[JsonValue] = [
        *(previous if isinstance(previous, list) else []),
        {
            "role": "assistant",
            "content": said.get("content"),
            "tool_calls": said.get("tool_calls"),
        },
        *(
            {"role": "tool", "tool_call_id": c.id, "content": results[c.id]}
            for c in calls
        ),
    ]
    return {**body, "messages": messages}
