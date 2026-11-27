from typing import Any

from pydantic import BaseModel, JsonValue

from chatddx.api import threads as api
from chatddx.bench import Bench
from chatddx.factors.base import resolve
from chatddx.factors.request import (
    INSERTS_BY_KIND,
    SLOTS_BY_PURPOSE,
    FewShot,
    Instructions,
    Output,
    Prompt,
)
from chatddx.factors.scoring import Expectation, ExpectationSchema, Scorer

from .fields import Field
from .scoring import code_of, scorer_choices

_TEXTS: dict[type[BaseModel], str] = {
    Instructions: "text",
    Output: "guidance",
    Prompt: "segments",
}
# Policy: a field earns its schema's form where what it holds is shaped by the schema;
# one that holds whatever a request or a template takes, or mostly whitespace, is
# clearer as JSON.
_FORMED: dict[type[BaseModel], str] = {FewShot: "messages", Output: "contract"}


def editors(
    bench: Bench, model: type[BaseModel], found: list[Field]
) -> dict[str, Any] | None:
    held = {f.name: f.value for f in found}
    open = {f.name for f in found if f.editable}
    fields: list[dict[str, Any]] = []
    scoring = None
    if (name := _TEXTS.get(model)) in open:
        kind = str(model.model_fields["kind"].default)
        fields.append(
            {
                "name": name,
                "as": "texts",
                "inserts": sorted(INSERTS_BY_KIND[kind]),
                "slots": {p: sorted(s) for p, s in SLOTS_BY_PURPOSE.items()}
                if model is Prompt
                else {},
            }
        )
    if model is Expectation and "data" in open:
        fields.append({"name": "data", "as": "schema", "of": "expectation_schema"})
    if model is Scorer and {"views", "params"} & open:
        try:
            code = code_of(bench, _text(held.get("entry_point")) or None)
        except KeyError:
            code = None
        if code is not None:
            views = held.get("views")
            judged = [
                judge
                for v in (views if isinstance(views, list) else [])
                if isinstance(v, dict) and isinstance(judge := v.get("judge"), str)
            ]
            scoring = scorer_choices(bench, code, judged)
            if "views" in open:
                fields.append(
                    {"name": "views", "as": "views", "of": "expectation_schema"}
                )
            if "params" in open and code.params.get("properties"):
                fields.append({"name": "params", "as": "schema", "schema": code.params})
    if (name := _FORMED.get(model)) in open:
        fields.append({"name": name, "as": "schema", "schema": _schema(model, name)})
    drawn = {f["name"] for f in fields}
    fields += [
        {"name": f.name, "as": "json", "brackets": f.brackets}
        for f in found
        if f.editable and f.shape == "json" and f.name not in drawn
    ]
    if not open:
        return None
    return {
        "fields": fields,
        "held": {
            k: v for k, v in held.items() if k in ("purpose", "expectation_schema")
        },
        "schemas": _schemas(bench)
        if any(f.get("of") == "expectation_schema" for f in fields)
        else {},
        "scoring": scoring,
    }


def _schema(model: type[BaseModel], name: str) -> dict[str, Any]:
    whole = model.model_json_schema()
    return {**whole["properties"][name], "$defs": whole.get("$defs", {})}


def _text(value: JsonValue) -> str:
    return value if isinstance(value, str) else ""


def _schemas(bench: Bench) -> dict[str, dict[str, JsonValue]]:
    return {
        t.head.digest: resolve(
            bench.store.get, t.head.digest, ExpectationSchema
        ).json_schema
        for t in api.threads(bench, "expectation_schema")
    }
