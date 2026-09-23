from typing import Any

import pytest

from chatddx.core.json_schema import satisfies

TEXT = {"type": "string"}
LIST_OF_TEXT = {"type": "array", "items": TEXT}

DIAGNOSIS_NAMES = {
    "type": "object",
    "required": ["diagnoses"],
    "properties": {
        "diagnoses": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["diagnosis"],
                "properties": {"diagnosis": TEXT},
            },
        },
    },
}

# the shape of management_plan_v1: what a contract needs is behind a `$ref`
PLAN = {
    "type": "object",
    "required": ["diagnoses", "sources"],
    "properties": {
        "sources": LIST_OF_TEXT,
        "diagnoses": {"type": "array", "items": {"$ref": "#/$defs/Diagnosis"}},
    },
    "$defs": {
        "Diagnosis": {
            "type": "object",
            "title": "Diagnosis",
            "required": ["diagnosis", "critical"],
            "properties": {
                "diagnosis": {"type": "string", "description": "Its name."},
                "critical": {"type": "boolean"},
            },
        },
    },
}


@pytest.mark.parametrize(
    "schema, contract, expected",
    [
        # annotations say nothing about which values are valid
        ({"type": "string", "title": "t", "description": "d"}, TEXT, True),
        (
            {"type": "array", "items": {"type": "string", "title": "t"}},
            LIST_OF_TEXT,
            True,
        ),
        # a contract that constrains nothing takes anything
        ({}, {}, True),
        ({"type": "integer"}, {"description": "anything"}, True),
        # types
        (TEXT, LIST_OF_TEXT, False),
        (LIST_OF_TEXT, TEXT, False),
        ({"type": "integer"}, {"type": "number"}, True),
        ({"type": "number"}, {"type": "integer"}, False),
        ({"type": ["string", "null"]}, TEXT, False),
        ({"type": ["string", "null"]}, {"type": ["null", "string"]}, True),
        # a schema without a type admits every type
        ({}, TEXT, False),
        # items
        ({"type": "array"}, LIST_OF_TEXT, False),
        ({"type": "array", "items": {"type": "integer"}}, LIST_OF_TEXT, False),
        ({"type": "array", "items": [TEXT]}, LIST_OF_TEXT, False),
        ({"type": "array", "items": False}, LIST_OF_TEXT, True),
        # a schema that lists its values is judged one value at a time
        ({"type": "array", "items": {"enum": ["a", "b"]}}, LIST_OF_TEXT, True),
        ({"type": "array", "items": {"enum": ["a", 1]}}, LIST_OF_TEXT, False),
        ({"type": "string", "enum": ["a", 1]}, TEXT, True),
        ({"const": "a"}, {"enum": ["a", "b"]}, True),
        (TEXT, {"enum": ["a", "b"]}, False),
        # unions and intersections, on either side
        ({"anyOf": [TEXT, {"type": "string", "maxLength": 3}]}, TEXT, True),
        ({"anyOf": [TEXT, {"type": "integer"}]}, TEXT, False),
        ({"allOf": [TEXT, {"maxLength": 3}]}, TEXT, True),
        (TEXT, {"anyOf": [{"type": "integer"}, TEXT]}, True),
        (TEXT, {"allOf": [TEXT, {"type": "integer"}]}, False),
        # objects: what the contract requires must be required, and each
        # property it describes must fit
        (PLAN, DIAGNOSIS_NAMES, True),
        (PLAN, {"type": "object", "required": ["warnings"]}, False),
        (
            {"type": "object", "properties": {"diagnoses": LIST_OF_TEXT}},
            DIAGNOSIS_NAMES,
            False,
        ),
        # a property the schema never has fits anything; one it may have as
        # anything fits nothing in particular
        (
            {"type": "object", "additionalProperties": False},
            {"type": "object", "properties": {"x": TEXT}},
            True,
        ),
        ({"type": "object"}, {"type": "object", "properties": {"x": TEXT}}, False),
        (
            {
                "type": "object",
                "additionalProperties": False,
                "patternProperties": {"^x": {"type": "integer"}},
            },
            {"type": "object", "properties": {"x": TEXT}},
            False,
        ),
        # what a contract says that this does not read, it cannot vouch for
        (LIST_OF_TEXT, {"type": "array", "minItems": 1}, False),
        (TEXT, {"oneOf": [TEXT]}, False),
        # a reference that leads nowhere could be anything
        ({"type": "array", "items": {"$ref": "#/$defs/missing"}}, LIST_OF_TEXT, False),
        (TEXT, {"$ref": "#/$defs/missing"}, False),
        # `false` admits nothing, so it fits every contract
        (False, TEXT, True),
        (TEXT, True, True),
        (TEXT, False, False),
    ],
)
def test_satisfies(schema: Any, contract: Any, expected: bool):
    assert satisfies(schema, contract) is expected


def test_schemas_that_refer_to_themselves_are_compared_as_far_as_they_unfold():
    def tree(leaf: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": leaf,
                "children": {"type": "array", "items": {"$ref": "#"}},
            },
        }

    assert satisfies(tree(TEXT), tree(TEXT)) is True
    assert satisfies(tree({"type": "string", "maxLength": 3}), tree(TEXT)) is True
    assert satisfies(tree({"type": "integer"}), tree(TEXT)) is False
    assert satisfies(tree(TEXT), tree({"enum": ["a"]})) is False
