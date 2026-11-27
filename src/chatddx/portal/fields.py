import json
import math
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, replace
from typing import Any, Literal, cast, get_args

from pydantic import BaseModel, JsonValue, ValidationError
from pydantic_core import ErrorDetails
from starlette.datastructures import FormData

from chatddx.api import schemas, threads as api
from chatddx.bench import Bench, word_of
from chatddx.factors import Invalid, Worded
from chatddx.factors.cases import Case
from chatddx.factors.engine import model_of
from chatddx.factors.request import Purpose
from chatddx.locale import display_language, tr

from .pages import own_first, refusal_of
from .titles import display_case

type Shape = Literal[
    "pick",
    "picks",
    "choose",
    "chooses",
    "number",
    "check",
    "lines",
    "text",
    "either",
    "json",
]


@dataclass(frozen=True)
class Field:
    name: str
    shape: Shape
    value: JsonValue
    editable: bool
    nullable: bool = False
    kinds: tuple[str, ...] = ()
    options: tuple[str, ...] = ()
    given: bool = True
    whole: bool = False
    minimum: int | float | None = None
    typed: str | None = None
    refused: str | None = None
    brackets: str | None = None


class _Unparsed(Invalid):
    pass


def fields(
    model: type[BaseModel], body: Mapping[str, JsonValue], editable: Collection[str]
) -> list[Field]:
    return [
        replace(
            _field(name, held, body.get(name), name in editable), given=name in body
        )
        for name, held in _properties(model).items()
    ]


def fresh(
    model: type[BaseModel], given: Mapping[str, str] | None = None
) -> list[Field]:
    given = given or {}
    properties = _properties(model)
    if unknown := [n for n in given if n not in properties]:
        raise Invalid.raw(
            "no field %(field)s to give: the fields are %(fields)s",
            field=repr(unknown[0]),
            fields=", ".join(properties),
        )
    return [
        replace(f, value=_read(f, given[f.name]), editable=False, given=True)
        if f.name in given
        else f
        for f in fields(model, defaults(model), properties)
    ]


def _read(f: Field, given: str) -> JsonValue:
    match f.shape:
        case "json" | "picks" | "chooses":
            return _json(f.name, given)
        case "number":
            return _number(f, given)
        case "check":
            return given == "true"
        case "lines":
            return _lines(f, given)
        case _:
            return given


def defaults(model: type[BaseModel]) -> dict[str, JsonValue]:
    return {
        name: cast(JsonValue, held["default"])
        for name, held in _properties(model).items()
        if "default" in held
    }


def _properties(model: type[BaseModel]) -> dict[str, dict[str, Any]]:
    properties = cast(
        dict[str, dict[str, Any]], model.model_json_schema()["properties"]
    )
    return {k: v for k, v in properties.items() if k not in ("kind", "v")}


def _field(name: str, held: dict[str, Any], value: JsonValue, editable: bool) -> Field:
    members: list[dict[str, Any]] = held.get("anyOf", [held])
    nullable = any(m.get("type") == "null" for m in members)
    rest = [m for m in members if m.get("type") != "null"]
    kinds = tuple(rest[0].get("x-kind", ())) if len(rest) == 1 else ()
    items: dict[str, Any] = rest[0].get("items", {}) if len(rest) == 1 else {}
    if kinds:
        return Field(name, "pick", value, editable, nullable, kinds)
    if "x-kind" in items:
        return Field(name, "picks", value, editable, nullable, tuple(items["x-kind"]))
    if "enum" in items or "const" in items:
        options = tuple(items.get("enum", [items.get("const")]))
        return Field(name, "chooses", value, editable, nullable, options=options)
    if rest and all("enum" in m or "const" in m for m in rest):
        options = [o for m in rest for o in m.get("enum", [m.get("const")])]
        return Field(name, "choose", value, editable, nullable, options=tuple(options))
    types = {m.get("type") for m in rest}
    if len(rest) == 1 and types <= {"integer", "number"} and types:
        whole = types == {"integer"}
        minimum = rest[0].get("minimum")
        return Field(
            name, "number", value, editable, nullable, whole=whole, minimum=minimum
        )
    if types == {"boolean"} and not nullable:
        return Field(name, "check", value, editable)
    if types == {"array"} and set(items) == {"type"} and items["type"] in _LISTED:
        whole = items["type"] == "integer"
        if whole or _one_a_line(value):
            return Field(name, "lines", value, editable, nullable, whole=whole)
    if types == {"string"}:
        return Field(name, "text", value, editable, nullable)
    if "string" in types:
        return Field(name, "either", value, editable, nullable)
    brackets = "{}" if types == {"object"} else "[]" if types == {"array"} else None
    return Field(name, "json", value, editable, nullable, brackets=brackets)


def choices(
    bench: Bench,
    kinds: tuple[str, ...],
    held: JsonValue,
    purpose: Purpose | None = None,
) -> list[tuple[str, str]]:
    found: dict[str, str] = {}
    if kinds == ("case",):
        for family in bench.families():
            bare = Case(vignette=family.vignette).digest
            for case in family.cases:
                named = (
                    family.name
                    if case == bare
                    else display_case(bench.titled_case(case))
                )
                _ = found.setdefault(case, named)
    elif set(kinds) <= _ENGINES:
        found = _engines(bench)
    else:
        login = bench.person.login
        for word in dict.fromkeys(word_of(k) for k in kinds):
            shown = [
                t
                for t, p in listed(bench, word)
                if None in (purpose, p) or p == purpose
            ]
            for t in own_first(bench, shown):
                named = t.name or t.title
                mine = t.owner in (None, login)
                _ = found.setdefault(
                    t.head.digest, named if mine else f"{t.owner}/{named}"
                )
    given = held if isinstance(held, list) else [held]
    for digest in given:
        if isinstance(digest, str) and digest not in found:
            found[digest] = _held(bench, digest, found)
    return list(found.items())


_ENGINES = frozenset({"engine.local", "engine.remote"})
_LISTED = frozenset({"string", "integer"})


def _one_a_line(value: JsonValue) -> bool:
    if not isinstance(value, list):
        return True
    return all(isinstance(v, str) and v and "\n" not in v for v in value)


# Policy: an engine is picked by its model's handle, as researchers see handles, not
# engines.
def _engines(bench: Bench) -> dict[str, str]:
    found: dict[str, str] = {}
    for t in own_first(bench, [t for t, _ in listed(bench, "model")]):
        handle = bench.handle(t.head.digest)
        if (engine := bench.latest(handle)) is not None:
            _ = found.setdefault(engine, handle.name)
    return found


def _held(bench: Bench, digest: str, found: Mapping[str, str]) -> str:
    if bench.rows.kind(digest) in _ENGINES:
        weights = model_of(digest, bench.store.get).digest
        return tr("%(model)s, an earlier engine", model=bench.handle(weights).name)
    for made in bench.rows.compilations(digest):
        if made.into is None:
            continue
        for head, named in found.items():
            if any(
                c.recipe == made.recipe and c.into is None
                for c in bench.rows.compilations(head)
            ):
                return tr(
                    "%(name)s, in %(language)s",
                    name=named,
                    language=display_language(made.into),
                )
    return tr("%(name)s, as it is held", name=bench.title(digest))


_PURPOSES: dict[str, Purpose] = {"trial": "generation", "judge": "judge"}


def purpose(model: type[BaseModel]) -> Purpose | None:
    kind = model.model_fields.get("kind")
    return None if kind is None else _PURPOSES.get(str(kind.default))


# Accommodating for the API, which lists configurations of one purpose at a time.
def listed(
    bench: Bench, word: str, deleted: bool = False
) -> list[tuple[schemas.Thread, Purpose | None]]:
    purposes = get_args(Purpose) if word == "configuration" else (None,)
    return [
        (t, p)
        for p in purposes
        for t in api.threads(bench, word, deleted=deleted, purpose=p)
    ]


def parsed(found: list[Field], form: FormData) -> dict[str, JsonValue]:
    body: dict[str, JsonValue] = {}
    for f in found:
        if not f.editable:
            body[f.name] = f.value
            continue
        given = _given(form, f.name)
        match f.shape:
            case "picks" | "chooses":
                picks = form.getlist(f"f.{f.name}")
                body[f.name] = list(
                    dict.fromkeys(v for v in picks if isinstance(v, str) and v)
                )
            case "pick" | "choose":
                if given or f.nullable:
                    body[f.name] = given or None
            case "number":
                if given.strip():
                    body[f.name] = _number(f, given.strip())
                elif f.nullable:
                    body[f.name] = None
            case "check":
                body[f.name] = given == "true"
            case "lines":
                body[f.name] = _lines(f, given)
            case "text":
                body[f.name] = None if given == "" and f.nullable else given
            case "either" if form.get(f"as.{f.name}") == "text":
                body[f.name] = None if given == "" and f.nullable else given
            case _:
                if given.strip():
                    body[f.name] = _json(f.name, _bracketed(f, given))
    return body


# Policy: a box whose field is an object or a list holds what is between its brackets,
# which the page shows around it, so that what is typed is of its shape whatever it is.
def _bracketed(f: Field, given: str) -> str:
    return given if f.brackets is None else f"{f.brackets[0]}{given}{f.brackets[1]}"


def _given(form: FormData, name: str) -> str:
    value = form.get(f"f.{name}", "")
    # Accommodating for browsers, which send a textarea's line breaks as CRLF.
    return value.replace("\r\n", "\n") if isinstance(value, str) else ""


def _number(f: Field, given: str) -> int | float:
    try:
        found = int(given) if f.whole else float(given)
    except ValueError:
        found = math.nan
    if not math.isfinite(found) and f.whole:
        raise _Unparsed.raw(
            "%(field)s isn't a whole number: %(given)s", field=f.name, given=repr(given)
        )
    if not math.isfinite(found):
        raise _Unparsed.raw(
            "%(field)s isn't a number: %(given)s", field=f.name, given=repr(given)
        )
    return found


# Policy: a list of whole numbers is read from whatever is typed, each whole number once,
# so that nothing typed in it is refused.
def _lines(f: Field, given: str) -> list[JsonValue]:
    if f.whole:
        return list(dict.fromkeys(int(n) for n in re.findall(r"\d+", given)))
    return [line for line in given.split("\n") if line]


def _json(name: str, given: str) -> JsonValue:
    try:
        return cast(JsonValue, json.loads(given))
    except json.JSONDecodeError as e:
        raise _Unparsed.of(
            "%(field)s isn't JSON: %(error)s", field=name, error=str(e)
        ) from None


def kept(
    found: list[Field], form: FormData, e: ValueError | None
) -> tuple[list[Field], list[str]]:
    names = [f.name for f in found if f.editable]
    by_field, rest = ({}, []) if e is None else _refusals(e, names)
    return [_kept(f, form, by_field.get(f.name)) for f in found], rest


def _refusals(
    e: ValueError, names: Collection[str]
) -> tuple[dict[str, str], list[str]]:
    if isinstance(e, _Unparsed) and (field := str(e.params["field"])) in names:
        return {field: refusal_of(e)}, []
    if not isinstance(e, ValidationError):
        return {}, [refusal_of(e)]
    by_field: dict[str, list[str]] = {}
    rest: list[str] = []
    for error in e.errors():
        at = [str(p) for p in error["loc"]]
        if at and at[0] in names:
            within = ".".join(at[1:])
            refusal = _refusal(error)
            by_field.setdefault(at[0], []).append(
                f"{within}: {refusal}" if within else refusal
            )
        else:
            rest.append(f"{'.'.join(at)}: {_refusal(error)}" if at else _refusal(error))
    return {n: "; ".join(refused) for n, refused in by_field.items()}, rest


def _refusal(error: ErrorDetails) -> str:
    if isinstance(cause := error.get("ctx", {}).get("error"), Worded):
        return refusal_of(cause)
    return error["msg"].removeprefix("Value error, ")


def _kept(f: Field, form: FormData, refused: str | None) -> Field:
    if not f.editable:
        return replace(f, refused=refused)
    given = _given(form, f.name)
    match f.shape:
        case "picks" | "chooses":
            picks = form.getlist(f"f.{f.name}")
            value: JsonValue = [v for v in picks if isinstance(v, str) and v]
        case "pick" | "choose":
            value = given or None
        case "check":
            value = given == "true"
        case "text":
            value = given
        case "either" if form.get(f"as.{f.name}") == "text":
            value = given
        case _:
            return replace(f, typed=given, refused=refused)
    return replace(f, value=value, refused=refused)
