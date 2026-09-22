from __future__ import annotations

import json
import logging
import tomllib
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import (
    IO,
    Any,
    get_args,
    get_origin,
)

from pydantic import (
    BaseModel,
    JsonValue,
    ValidationError,
)
from rich.pretty import pretty_repr

from chatddx.core import settings
from chatddx.dx.error_handling import print_pydantic_errors
from chatddx.repo.bundles import entity_of
from chatddx.repo.families.pydantic import BranchDetailsPatch
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.registry import EntityName
from chatddx.repo.todo import all_entities
from chatddx.utils import is_str_list

logger = logging.getLogger(__name__)


class ParseError(Exception):
    pass


FileLoader = Callable[[IO[bytes]], JsonValue]
FileLoaders = dict[str, FileLoader]

# The three levels of an inventory file, named so the indexing reads:
#   registry[entity][name][field]
Record = dict[str, JsonValue]
EntityTable = dict[str, Record]
DictRegistry = dict[str, EntityTable]

# A record with its references resolved and its parents merged in. Values are
# `Any` because a field may now hold a nested `EntityData` rather than the
# `JsonValue` that was read off disk.
EntityData = dict[str, Any]

ParsedEntry = tuple[BaseModel, BranchDetailsPatch]
Inventory = dict[EntityName, dict[str, ParsedEntry]]

KEYWORDS = frozenset({"extends", "partial"})


@dataclass
class EntityContext:
    get_record: Callable[[type[BaseModel], EntityContext], Record]
    data: DictRegistry
    schema: type[BaseModel]


def _read_text(f: IO[bytes]) -> JsonValue:
    return f.read().decode("utf-8").rstrip("\n")


LOADERS: FileLoaders = {
    ".toml": tomllib.load,
    ".json": json.load,
    ".txt": _read_text,
}


def branch_details_keys(entity: EntityName) -> frozenset[str]:
    """
    What this entity carries beside its content, by name. A key an entity
    does not carry is not branch details, so it falls through to the trail
    schema -- where it is an unknown field and says so.
    """
    return frozenset(entity_of(entity).branch_details_patch.model_fields)


def find_field(schema: object) -> EntityName | None:
    """
    The entity a trail schema belongs to, or None for anything that is not
    one (a plain value, a nested non-entity model).

    This asks the registry rather than reverse-searching the inventory's
    field types, so there is one answer to "which entity is this class?"
    and not two that can drift apart.
    """
    if not isinstance(schema, type):
        return None

    try:
        return entity_of(schema).name
    except (KeyError, TypeError):
        return None


def _lookup(data: DictRegistry, entity: EntityName, name: str) -> Record:
    """One named record, or a ParseError naming what is missing."""
    table = data.get(entity)

    if table is None:
        raise ParseError(f"no '{entity}' entries defined, needed by '{name}'")

    try:
        return table[name]
    except KeyError:
        raise ParseError(f"unknown {entity} '{name}'") from None


def parse_entity(
    schema: type[BaseModel],
    entity: EntityName,
    name: str,
    values: Record,
    data: DictRegistry,
) -> EntityData:
    base_data: EntityData = {}
    passthrough = KEYWORDS | branch_details_keys(entity)

    for field_name, field_value in values.items():
        if field_name in passthrough:
            base_data[field_name] = field_value
            continue

        try:
            field_schema = schema.model_fields[field_name].annotation
        except KeyError:
            if settings.MODE == "dev":
                formatted_values = pretty_repr(values, indent_size=4)
                logger.warning(
                    f"Field '{field_name}' not found in schema {schema.__name__} "
                    + f"for '{name}'. Provided values:\n{formatted_values}"
                )
            raise

        if get_origin(field_schema) is list:
            inner_schema = get_args(field_schema)[0]
            inner_entity = find_field(inner_schema)

            if inner_entity is not None:
                if not is_str_list(field_value):
                    raise ParseError(
                        f"expected a list of {inner_entity} names for "
                        + f"'{field_name}', got {field_value!r}"
                    )

                base_data[field_name] = [
                    parse_entity(
                        inner_schema,
                        inner_entity,
                        field_name,
                        _lookup(data, inner_entity, item),
                        data,
                    )
                    for item in field_value
                ]
                continue

        field_entity = find_field(field_schema)

        if field_schema is None or field_entity is None or field_value is None:
            base_data[field_name] = field_value
            continue

        match field_value:
            case str():
                base_data[field_name] = parse_entity(
                    field_schema,
                    field_entity,
                    field_name,
                    _lookup(data, field_entity, field_value),
                    data,
                )
            case list() if field_value and is_str_list(field_value):
                head, *rest = field_value

                extended: Record = dict(_lookup(data, field_entity, head))
                extended["extends"] = [*rest]

                base_data[field_name] = parse_entity(
                    field_schema,
                    field_entity,
                    head,
                    extended,
                    data,
                )
            case dict():
                base_data[field_name] = parse_entity(
                    field_schema,
                    field_entity,
                    field_name,
                    field_value,
                    data,
                )
            case _:
                raise ParseError(
                    f"unexpected value for '{field_name}': {field_value!r}"
                )

    base_data["name"] = name

    extends = base_data.get("extends")

    if not extends:
        return base_data

    if isinstance(extends, str):
        extends = [extends]

    if not is_str_list(extends):
        raise ParseError(
            "'extends' must be a name or a list of names, "
            + f"got {extends!r} for '{name}'"
        )

    base_data["extends"] = extends

    for ext_name in extends:
        # base_data["name"] += "|" + ext_name
        ext_data = parse_entity(
            schema,
            entity,
            ext_name,
            _lookup(data, entity, ext_name),
            data,
        )
        base_data = merge_entities(base_data, ext_data)

    return base_data


def merge_entities(base: EntityData, ext: EntityData) -> EntityData:
    return ext | base


def parse(
    path: Path, branch_details: BranchDetailsPatch | None = None
) -> ParsedInventory:
    data = _from_file(path)
    inventory: Inventory = {}

    if branch_details is None:
        branch_details = BranchDetailsPatch()

    patch = branch_details.model_dump(exclude_none=True)

    for entity in all_entities:
        entries: dict[str, ParsedEntry] = {}
        inventory[entity] = entries

        table = data.get(entity)

        if table is None:
            continue

        bundle = entity_of(entity)
        entity_schema = bundle.trail_schema
        details_cls = bundle.branch_details_patch
        details_keys = branch_details_keys(entity)

        for name, values in table.items():
            if values.get("partial"):
                continue

            entity_data = parse_entity(
                entity_schema,
                entity,
                name,
                values,
                data,
            )

            # `entity_data` holds the trail's fields too, so hand the
            # patch only the keys it declares
            named = {
                key: value for key, value in entity_data.items() if key in details_keys
            }

            try:
                entity_branch_details = details_cls.model_validate(named | patch)
                trail = entity_schema.model_validate(entity_data)

            except ValidationError as e:
                print_pydantic_errors(e)
                raise

            entries[name] = trail, entity_branch_details

    try:
        return ParsedInventory.model_validate(inventory)
    except ValidationError as e:
        print_pydantic_errors(e)
        raise


def _load(path: Path, loaders: FileLoaders) -> JsonValue:
    try:
        loader = loaders[path.suffix]
    except KeyError:
        raise ParseError(f"no loader for '{path.suffix}' files: {path}") from None

    with path.open("rb") as f:
        return loader(f)


def _from_file(
    path: Path,
    seen: list[Path] | None = None,
) -> DictRegistry:
    if seen is None:
        seen = []

    resolved_path = path.resolve()
    if resolved_path in seen:
        loop = " -> ".join([p.name for p in seen] + [path.name])
        raise ParseError(f"Circular dependency detected in 'extends': {loop}")

    current_seen = seen + [resolved_path]

    data = _load(resolved_path, LOADERS)

    if not isinstance(data, dict):
        raise ParseError(
            f"Inventory file '{path}' must contain a top-level object, "
            + f"got {type(data).__name__}"
        )

    resolved_data = resolve_imports(
        preprocess(data),
        LOADERS,
        path.parent,
        current_seen,
    )

    if not isinstance(resolved_data, dict):
        raise ParseError(
            f"Inventory file '{path}' must contain a top-level object, "
            + f"got {type(resolved_data).__name__}"
        )

    extends = resolved_data.pop("extends", [])
    match extends:
        case str():
            extend_paths = [extends]
        case list() if is_str_list(extends):
            extend_paths = extends
        case _:
            raise ParseError(
                f"'extends' must be a path or a list of paths, got {extends!r}"
            )

    registry = as_registry(resolved_data, path)

    for extend_path in extend_paths:
        extend_dict = _from_file(path.parent / extend_path, current_seen)
        registry = extend_registries(registry, extend_dict)

    return registry


def as_registry(data: Mapping[str, JsonValue], path: Path) -> DictRegistry:
    """
    Check on the way in that the file has the entity -> name -> record shape
    the rest of the parser indexes into, so a malformed file is reported
    here and not as a KeyError three frames down.
    """
    registry: DictRegistry = {}

    for entity, table in data.items():
        if not isinstance(table, dict):
            raise ParseError(
                f"'{entity}' in '{path}' must be a table of named entries, "
                + f"got {type(table).__name__}"
            )

        entries: EntityTable = {}

        for name, record in table.items():
            if not isinstance(record, dict):
                raise ParseError(
                    f"'{entity}.{name}' in '{path}' must be a table, "
                    + f"got {type(record).__name__}"
                )
            entries[name] = record

        registry[entity] = entries

    return registry


def preprocess(raw_data: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Add exceptions before any processing"""

    data = deepcopy(raw_data)

    agents = data.get("agent", {})
    for agent, agent_data in agents.items():
        bundle_the_instruction(agent, agent_data)

    cases = data.get("case")

    if cases is None:
        return data

    if not isinstance(cases, dict):
        raise ParseError(f"'case' must be a table, got {type(cases).__name__}")

    generated: dict[str, JsonValue] = {}

    for case, case_data in cases.items():
        if not isinstance(case_data, dict):
            raise ParseError(
                f"'case.{case}' must be a table, got {type(case_data).__name__}"
            )

        if "payload" not in case_data:
            _ = case_data.setdefault("payload_path", f"cases/{case}.txt")

        expects = case_data.get("expects")

        if not isinstance(expects, dict):
            continue

        names: list[JsonValue] = []

        for scorer, payload in expects.items():
            expect_name = f"{case}|{scorer}"
            generated[expect_name] = {
                "scorer": scorer,
                "payload": payload,
            }
            names.append(expect_name)

        case_data["expects"] = names

    if generated:
        expect = data.setdefault("expect", {})

        if not isinstance(expect, dict):
            raise ParseError(f"'expect' must be a table, got {type(expect).__name__}")

        expect.update(generated)

    return data


def bundle_the_instruction(agent: str, agent_data: JsonValue) -> None:
    for flat, bundled in (
        ("instructions", "definition"),
        ("instructions_path", "definition_path"),
    ):
        if flat not in agent_data:
            continue

        if "instruction" in agent_data:
            raise ParseError(
                f"Both '{flat}' and 'instruction' are defined on agent "
                + f"'{agent}', pick one."
            )

        agent_data["instruction"] = {bundled: agent_data.pop(flat)}


def extend_registries(base: DictRegistry, update: DictRegistry) -> DictRegistry:
    for key, value in update.items():
        base_val = base.get(key, {})
        base[key] = value | base_val
    return base


def resolve_imports(
    obj: JsonValue,
    loaders: FileLoaders,
    base_path: Path,
    seen: list[Path] | None = None,
) -> JsonValue:

    if seen is None:
        seen = []

    if isinstance(obj, dict):
        new_obj: dict[str, JsonValue] = {}

        for key, value in obj.items():
            if not key.endswith("_path"):
                new_obj[key] = resolve_imports(
                    value,
                    loaders,
                    base_path,
                    seen,
                )
                continue

            if not isinstance(value, str):
                raise ParseError(f"'{key}' is expected to be a string, was {value!r}")

            key = key.removesuffix("_path")

            if key in obj:
                raise ParseError(
                    f"Both '{key}_path' and '{key}' are defined, pick one. '{obj}'"
                )

            path = (base_path / value).resolve()

            if path in seen:
                loop = " -> ".join([p.name for p in seen] + [path.name])
                raise ParseError(f"Circular dependency detected in 'extends': {loop}")

            new_obj[key] = resolve_imports(
                _load(path, loaders),
                loaders,
                path.parent,
                seen + [path],
            )

        return new_obj

    if isinstance(obj, list):
        return [
            resolve_imports(
                item,
                loaders,
                base_path,
                seen,
            )
            for item in obj
        ]

    return obj
