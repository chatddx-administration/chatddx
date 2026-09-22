"""
Whether every value one JSON Schema admits is admitted by another.

That is the question behind "can this scorer read that output type": an
output type's definition says what a run can return, a scorer's contract
says what it can judge, and the scorer can read the output type when the
first fits inside the second.

It cannot be decided for schemas in general, so `satisfies` answers yes only
where it can see it -- for the keywords below, which is how definitions and
contracts are written here -- and no everywhere else. A pairing it misses is
one somebody has to make by hand; one it wrongly claims is a batch of runs
that fail at scoring, so it errs the first way.
"""

from collections.abc import Mapping, Sequence
from typing import Any, cast

import jsonschema

# Keywords that say nothing about which values are valid, read past on
# either side.
ANNOTATIONS = frozenset(
    {
        "$comment",
        "$defs",
        "$id",
        "$schema",
        "default",
        "definitions",
        "deprecated",
        "description",
        "examples",
        "readOnly",
        "title",
        "writeOnly",
    }
)

# What a contract may constrain for `satisfies` to have an answer. A contract
# that says anything else is one it cannot vouch for.
CONTRACT_KEYWORDS = frozenset(
    {
        "type",
        "enum",
        "const",
        "items",
        "properties",
        "required",
        "anyOf",
        "allOf",
    }
)

JSON_TYPES = frozenset(
    {"array", "boolean", "integer", "null", "number", "object", "string"}
)

# Deep enough for any definition written by hand, and a stop for one that
# refers to itself.
MAX_DEPTH = 64

type Schema = Mapping[str, Any] | bool


def satisfies(schema: Schema, contract: Schema) -> bool:
    """
    Whether every value `schema` admits is one `contract` admits too.

    Read as draft 7, which is what a definition is checked against
    (`chatddx.core.fields.validate_json_schema`): a `$ref` stands for what
    it points at, and whatever sits beside it is ignored.
    """
    return _Comparison(schema, contract).satisfies(schema, contract, 0)


class _Comparison:
    def __init__(self, schema_root: Schema, contract_root: Schema):
        self.schema_root: Schema = schema_root
        self.contract_root: Schema = contract_root
        # The pairs being compared further up. A schema that refers to itself
        # meets the same pair again below, and a pair that fits as far as it
        # unfolds fits: the one way the comparison of two recursive schemas
        # ends in a yes.
        self.assumed: set[tuple[int, int]] = set()

    def satisfies(self, schema: Schema, contract: Schema, depth: int) -> bool:
        if depth > MAX_DEPTH:
            return False

        resolved_schema = _resolve(schema, self.schema_root)
        resolved_contract = _resolve(contract, self.contract_root)

        # A reference that cannot be followed could stand for anything: on
        # the schema's side that is everything, and on the contract's side
        # nothing it can vouch for.
        if resolved_contract is None:
            return False

        schema = True if resolved_schema is None else resolved_schema
        contract = resolved_contract

        # `false` admits nothing and `true` everything
        if schema is False or contract is True:
            return True
        if contract is False:
            return False
        if schema is True:
            schema = {}

        assert isinstance(schema, Mapping) and isinstance(contract, Mapping)

        pair = (id(schema), id(contract))

        if pair in self.assumed:
            return True

        self.assumed.add(pair)

        try:
            return self.compare(schema, contract, depth)
        finally:
            self.assumed.discard(pair)

    def compare(
        self,
        schema: Mapping[str, Any],
        contract: Mapping[str, Any],
        depth: int,
    ) -> bool:
        constraints = {
            key: value for key, value in contract.items() if key not in ANNOTATIONS
        }

        if not constraints:
            return True

        if not constraints.keys() <= CONTRACT_KEYWORDS:
            return False

        # A schema that lists its values is judged one value at a time.
        values = self.values(schema)

        if values is not None:
            return all(self.admits(contract, value) for value in values)

        return self.union(schema, contract, depth) or self.parts(
            schema, contract, constraints, depth
        )

    def union(
        self,
        schema: Mapping[str, Any],
        contract: Mapping[str, Any],
        depth: int,
    ) -> bool:
        """
        A schema that is a union fits when every branch does, and one that is
        an intersection when any of its parts does. Short of that, its other
        keywords are what is left to go on -- ignoring a combinator only ever
        makes a schema admit more, so what is proven without it still holds.
        """
        for keyword in ("anyOf", "oneOf"):
            branches = schema.get(keyword)

            if branches and all(
                self.satisfies(branch, contract, depth + 1) for branch in branches
            ):
                return True

        return any(
            self.satisfies(part, contract, depth + 1)
            for part in schema.get("allOf", ())
        )

    def parts(
        self,
        schema: Mapping[str, Any],
        contract: Mapping[str, Any],
        constraints: Mapping[str, Any],
        depth: int,
    ) -> bool:
        if "anyOf" in constraints:
            rest = {key: value for key, value in contract.items() if key != "anyOf"}

            return self.satisfies(schema, rest, depth + 1) and any(
                self.satisfies(schema, branch, depth + 1)
                for branch in constraints["anyOf"]
            )

        if "allOf" in constraints:
            rest = {key: value for key, value in contract.items() if key != "allOf"}

            return self.satisfies(schema, rest, depth + 1) and all(
                self.satisfies(schema, part, depth + 1) for part in constraints["allOf"]
            )

        # A contract that lists its values can only be met by a schema that
        # lists its own, and those were judged above.
        if "enum" in constraints or "const" in constraints:
            return False

        schema_types = _types(schema) or JSON_TYPES
        contract_types = _types(contract)

        if contract_types is not None and not all(
            kind in contract_types or (kind == "integer" and "number" in contract_types)
            for kind in schema_types
        ):
            return False

        if "array" in schema_types and not self.array(schema, constraints, depth):
            return False

        return "object" not in schema_types or self.object(schema, constraints, depth)

    def array(
        self,
        schema: Mapping[str, Any],
        constraints: Mapping[str, Any],
        depth: int,
    ) -> bool:
        if "items" not in constraints:
            return True

        items: Any = schema.get("items", True)
        contract_items: Any = constraints["items"]

        # items given one schema per position is more than this reads
        if not isinstance(items, (Mapping, bool)) or not isinstance(
            contract_items, (Mapping, bool)
        ):
            return False

        return self.satisfies(
            cast(Schema, items),
            cast(Schema, contract_items),
            depth + 1,
        )

    def object(
        self,
        schema: Mapping[str, Any],
        constraints: Mapping[str, Any],
        depth: int,
    ) -> bool:
        if not set(constraints.get("required", ())) <= set(schema.get("required", ())):
            return False

        properties: Mapping[str, Any] = schema.get("properties", {})
        additional: Schema = schema.get("additionalProperties", True)

        for name, contract_property in constraints.get("properties", {}).items():
            # A property the schema does not describe is whatever its
            # `additionalProperties` allows -- and with that `false`, never
            # there at all -- unless a pattern lets it in, which is more than
            # this reads.
            if name in properties:
                schema_property = properties[name]
            elif "patternProperties" in schema:
                schema_property = True
            else:
                schema_property = additional

            if not self.satisfies(schema_property, contract_property, depth + 1):
                return False

        return True

    def values(self, schema: Mapping[str, Any]) -> list[Any] | None:
        if "const" in schema:
            listed: Sequence[Any] = [schema["const"]]
        elif "enum" in schema:
            listed = schema["enum"]
        else:
            return None

        # the keywords beside a list narrow it further
        return [value for value in listed if self.admits(schema, value, schema=True)]

    def admits(
        self,
        node: Mapping[str, Any],
        value: Any,
        schema: bool = False,
    ) -> bool:
        root = self.schema_root if schema else self.contract_root
        definitions: Mapping[str, Any] = root if isinstance(root, Mapping) else {}

        # A node reached from inside a root refers to that root's definitions,
        # so it is validated with them in reach.
        try:
            jsonschema.validate(
                instance=value,
                schema={
                    **node,
                    "$defs": definitions.get("$defs", {}),
                    "definitions": definitions.get("definitions", {}),
                },
                cls=jsonschema.Draft7Validator,
            )
        except (jsonschema.ValidationError, jsonschema.SchemaError):
            return False

        return True


def _types(schema: Mapping[str, Any]) -> frozenset[str] | None:
    kind = schema.get("type")

    match kind:
        case None:
            return None
        case str():
            return frozenset({kind})
        case _:
            return frozenset(kind)


def _resolve(schema: Schema, root: Schema) -> Schema | None:
    """
    What a schema stands for once its `$ref`s are followed -- only references
    into the same document, which is all a definition can hold -- or None
    where one cannot be followed.
    """
    seen: set[str] = set()

    while isinstance(schema, Mapping) and "$ref" in schema:
        ref = schema["$ref"]

        if not isinstance(ref, str) or not ref.startswith("#") or ref in seen:
            return None

        seen.add(ref)
        target = _pointer(root, ref[1:])

        if target is None:
            return None

        schema = target

    return schema


def _pointer(root: Schema, pointer: str) -> Schema | None:
    node: Any = root

    for step in pointer.split("/")[1:]:
        step = step.replace("~1", "/").replace("~0", "~")

        if not isinstance(node, Mapping) or step not in node:
            return None

        node = node[step]

    return cast(Schema, node) if isinstance(node, (Mapping, bool)) else None
