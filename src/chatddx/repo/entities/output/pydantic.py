"""
Output: a request-time slice.

A variation is what is asked for: a JSON Schema, or none for free text; the
guidance that fills the instruction's `output_guidance` slot, which says what
to produce and in what order; and the views it offers scorers.

A scorer never reads an output, a mode or a transcript. It reads a view: a
named, typed reading of the output. A structured output gives each view as a
path into its schema, in a subset of JSONPath (names, `[*]`, and a filter
`[?(@.name)]` that keeps the items whose boolean `name` is true), and free
text gives a parser. The path is proved against the schema here, when the
output is committed, so pairing a scorer with an output is set membership:
does the output offer the scorer's view? An output offers only what it
declares, `text` included.

The schema is kept as written, key order included: a constrained decoder
emits keys in the order `properties` gives them.
"""

import json
import re
from typing import Any, Literal, cast, get_args

from pydantic import Field, JsonValue, model_validator

from chatddx.core.fields import CoercedStr
from chatddx.repo.families import (
    ORDERED,
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchIn,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
    TrailRef,
)
from chatddx.repo.families.fields import JsonSchema

# The readings of an output a scorer can ask for, each offered by the
# outputs that declare it. `text` is an answer as written, `differential`
# the diagnoses, most likely first, `warning` and `disposition` a
# management plan's red flags and where the patient goes, and `critical`
# the diagnoses the answer marks critical.
type View = Literal["text", "differential", "warning", "disposition", "critical"]
VIEWS: tuple[View, ...] = get_args(View.__value__)

# What each view yields one of: its items' JSON type, and whether a null
# may stand in for one, and reads as nothing: a plan with no red flags.
VIEW_ITEMS: dict[View, tuple[str, bool]] = {
    "text": ("string", False),
    "differential": ("string", False),
    "warning": ("string", True),
    "disposition": ("string", False),
    "critical": ("string", False),
}

# Free text's parsers, by the view each gives. `lines`: one item per
# non-empty line, list markers stripped. `whole`: the answer as written.
PARSERS: dict[str, View] = {"lines": "differential", "whole": "text"}

# the instruction's variable the guidance fills
SLOT = "output_guidance"

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_PATH = re.compile(rf"\$(?:\.{_NAME}|\[\*\]|\[\?\(@\.{_NAME}\)\])*")
_STEP = re.compile(rf"\.({_NAME})|\[\*\]|\[\?\(@\.({_NAME})\)\]")


# a list marker the `lines` parser strips: `-`, `*`, `•`, `1.` or `1)`
_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


class Unproved(ValueError):
    pass


def read(document: JsonValue, path: str) -> list[JsonValue]:
    """
    Every value `path` reaches in `document`, in the document's order; a
    null is nothing reached.
    """
    values: list[JsonValue] = [document]

    for step in _STEP.finditer(path, 1):
        name, flag = step.group(1), step.group(2)
        reached: list[JsonValue] = []

        for value in values:
            if name is not None and isinstance(value, dict) and name in value:
                reached.append(value[name])
            elif name is None and isinstance(value, list):
                reached.extend(
                    item
                    for item in value
                    if flag is None
                    or (isinstance(item, dict) and item.get(flag) is True)
                )

        values = reached

    return [value for value in values if value is not None]


def lines(text: str) -> list[str]:
    """The `lines` parser: an item per non-empty line, its list marker stripped."""
    items = (_MARKER.sub("", line).strip() for line in text.splitlines())
    return [item for item in items if item]


def whole(text: str) -> list[str]:
    """The `whole` parser: the answer as written, unless it is blank."""
    return [text] if text.strip() else []


PARSE = {"lines": lines, "whole": whole}


def prove(
    schema: dict[str, JsonValue], path: str, items: str, nullable: bool = False
) -> None:
    """
    Raise `Unproved` unless every value `path` yields, from any document
    `schema` accepts, is of JSON type `items`, or null where `nullable`.
    Conservative: whatever it can't follow (a union, a nullable step, a
    reference outside the document) it refuses.
    """
    node = _resolve(schema, schema)
    here = "$"

    for step in _STEP.finditer(path, 1):
        name = step.group(1)

        if name is not None:
            _expect(node, "object", here)
            properties = node.get("properties")

            if not isinstance(properties, dict) or name not in properties:
                raise Unproved(f"{here} has no property '{name}'")

            node = _resolve(schema, properties[name])
            here = f"{here}.{name}"
        else:
            flag = step.group(2)
            _expect(node, "array", here)
            node = _resolve(schema, node.get("items"))

            if flag is None:
                here = f"{here}[*]"
                continue

            here = f"{here}[?(@.{flag})]"
            _expect(node, "object", here)
            properties = node.get("properties")

            if not isinstance(properties, dict) or flag not in properties:
                raise Unproved(f"{here} filters on '{flag}', which it doesn't declare")

            _expect(_resolve(schema, properties[flag]), "boolean", f"{here}.{flag}")

    _expect(node, items, here, nullable)


def _expect(node: dict[str, Any], kind: str, here: str, nullable: bool = False) -> None:
    declared = node.get("type")

    if declared == kind:
        return

    if nullable and declared in ([kind, "null"], ["null", kind]):
        return

    if kind == "string" and declared is None:
        choices = node["enum"] if "enum" in node else [node.get("const")]

        if choices and all(isinstance(choice, str) for choice in choices):
            return

    raise Unproved(
        f"{here} is {_describe(node)}, not {'an' if kind[0] in 'ao' else 'a'} {kind}"
    )


def _resolve(schema: dict[str, Any], node: Any) -> dict[str, Any]:
    seen: list[str] = []

    while isinstance(node, dict) and "$ref" in node:
        ref: object = cast(dict[str, Any], node)["$ref"]

        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            raise Unproved(f"can't follow the reference {ref!r}")

        seen.append(ref)
        node = schema

        for part in ref[2:].split("/"):
            node = (
                cast(dict[str, Any], node).get(part) if isinstance(node, dict) else None
            )

    if not isinstance(node, dict):
        raise Unproved(f"{node!r} is not a schema")

    return cast(dict[str, Any], node)


def _describe(node: dict[str, Any]) -> str:
    for keyword in ("anyOf", "oneOf", "allOf"):
        if keyword in node:
            return f"a union ({keyword})"

    declared = node.get("type")

    if declared is None:
        return "of no declared type"

    return f"of type {declared}"


class OutputTrailBase(BaseTrail):
    json_schema: JsonSchema | None = Field(
        default=None, json_schema_extra={ORDERED: True}
    )
    guidance: str | None = None
    views: dict[View, str] = Field(default_factory=dict)

    def view(self, name: View, answer: JsonValue) -> list[JsonValue]:
        """
        What the view `name` reads from `answer`: the values its path
        reaches in a structured answer, or its parser's items from free
        text.
        """
        reading = self.views[name]

        if self.json_schema is None:
            text = answer if isinstance(answer, str) else json.dumps(answer)
            return list(PARSE[reading](text))

        return read(answer, reading)

    @model_validator(mode="after")
    def _every_view_is_proved(self):
        for view, reading in self.views.items():
            if self.json_schema is None:
                if PARSERS.get(reading) != view:
                    parsers = [name for name, gives in PARSERS.items() if gives == view]
                    raise ValueError(
                        f"free text gives its '{view}' view through a parser "
                        + f"({', '.join(parsers)}), not {reading!r}"
                    )
                continue

            if not _PATH.fullmatch(reading):
                raise ValueError(
                    f"'{view}' reads {reading!r}, which is not a path of names, "
                    + "[*] and [?(@.name)] from $"
                )

            try:
                prove(self.json_schema, reading, *VIEW_ITEMS[view])
            except Unproved as e:
                raise ValueError(
                    f"'{view}' reads {reading}, and the schema doesn't prove it: {e}"
                ) from None

        return self


class OutputTrailIn(OutputTrailBase, TrailIn):
    pass


class OutputTrailRef(TrailRef, OutputTrailBase):
    pass


class OutputTrailOut(OutputTrailBase, TrailOut):
    pass


class OutputBranchIn(BranchIn[OutputTrailIn]):
    pass


class OutputBranchOut(BranchOut[OutputTrailOut, Details]):
    pass


class OutputFormDataIn(OutputTrailBase, BaseFormDataIn):
    pass


class OutputFormDataOut(OutputTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
