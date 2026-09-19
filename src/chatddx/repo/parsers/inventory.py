from __future__ import annotations

import json
import logging
import tomllib
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import (
    IO,
    Any,
    cast,
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
from chatddx.repo.bundles import entity_of
from chatddx.repo.families.pydantic import BranchDetailsPatch
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.registry import EntityName
from chatddx.repo.todo import all_entities

logger = logging.getLogger(__name__)


class ParseError(Exception):
    pass


FileLoaders = dict[str, Callable[[IO[bytes]], JsonValue]]

Record = dict[str, Any]
DictRegistry = dict[str, Record]

KEYWORDS = {"extends", "partial"}


@dataclass
class EntityContext:
    get_record: Callable[[type[BaseModel], EntityContext], Record]
    data: DictRegistry
    schema: type[BaseModel]


def branch_details_keys(entity: EntityName) -> set[str]:
    """
    What this entity carries beside its content, by name. A key an entity
    does not carry is not branch details, so it falls through to the trail
    schema -- where it is an unknown field and says so.
    """
    return set(entity_of(entity).branch_details_patch.model_fields.keys())


def find_field(schema: type[Any] | None) -> EntityName | None:
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


def parse_entity(
    schema: type[Any],
    entity: EntityName,
    name: str,
    values: dict[str, Any],
    data: dict[EntityName, dict[str, Any]],
) -> Any:
    base_data: dict[str, Any] = {}

    for field_name, field_value in values.items():
        if field_name in KEYWORDS | branch_details_keys(entity):
            base_data[field_name] = field_value
            continue

        try:
            field_schema = schema.model_fields[field_name].annotation
        except KeyError:
            if settings.MODE == "dev" and field_name not in schema.model_fields:
                formatted_values = pretty_repr(values, indent_size=4)
                logger.warning(
                    f"Field '{field_name}' not found in schema {schema.__name__} for '{name}'. "
                    + f"Provided values:\n{formatted_values}"
                )
            raise

        if get_origin(field_schema) is list:
            inner_field_schema = get_args(field_schema)[0]
            inner_field_entity = find_field(inner_field_schema)

            if inner_field_entity is not None:
                base_data[field_name] = [
                    parse_entity(
                        inner_field_schema,
                        inner_field_entity,
                        field_name,
                        data[inner_field_entity][v],
                        data,
                    )
                    for v in field_value
                ]
                continue

        field_entity = find_field(field_schema)

        if field_entity is None or field_value is None:
            base_data[field_name] = field_value
            continue

        match field_value:
            case str():
                base_data[field_name] = parse_entity(
                    field_schema,
                    field_entity,
                    field_name,
                    data[field_entity][field_value],
                    data,
                )
            case list():
                assert len(field_value) > 0
                base_data[field_name] = parse_entity(
                    field_schema,
                    field_entity,
                    field_value[0],
                    data[field_entity][field_value[0]]
                    | {
                        "extends": field_value[1:],
                    },
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
                raise ParseError(f"unexpected data type {type(field_value)}")

    base_data["name"] = name

    if not base_data.get("extends"):
        return base_data

    if isinstance(base_data["extends"], str):
        base_data["extends"] = [base_data["extends"]]

    for ext_name in base_data["extends"]:
        # base_data["name"] += "|" + ext_name
        ext_data = parse_entity(
            schema,
            entity,
            ext_name,
            data[entity][ext_name],
            data,
        )
        base_data = merge_entities(base_data, ext_data)

    return base_data


def merge_entities(base: dict[str, Any], ext: dict[str, Any]):
    return ext | base


def parse(
    path: Path, branch_details: BranchDetailsPatch | None = None
) -> ParsedInventory:
    data = _from_file(path)
    inventory: object = {}

    if branch_details is None:
        branch_details = BranchDetailsPatch()

    for entity in all_entities:
        inventory[entity] = {}

        if entity not in data:
            continue

        entity_schema = entity_of(entity).trail_schema

        for name, values in data[entity].items():
            if isinstance(values, dict) and values.get("partial"):  # pyright: ignore[reportUnknownMemberType]
                continue

            entity_data = parse_entity(
                entity_schema,
                entity,
                name,
                values,
                data,
            )

            try:
                # `entity_data` holds the trail's fields too, so hand the
                # patch only the keys it declares
                details_cls = entity_of(entity).branch_details_patch
                named = {
                    key: value
                    for key, value in entity_data.items()
                    if key in branch_details_keys(entity)
                }

                entity_branch_details = details_cls.model_validate(
                    named | branch_details.model_dump(exclude_none=True)
                )

                trail = entity_schema.model_validate(entity_data)

            except ValidationError as e:
                print_pydantic_errors(e)
                raise

            inventory[entity][name] = trail, entity_branch_details

    try:
        return ParsedInventory.model_validate(inventory)
    except ValidationError as e:
        print_pydantic_errors(e)
        raise


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

    def txt(f: IO[bytes]) -> str:
        content = f.read().decode("utf-8").rstrip("\n")
        return content

    loaders: FileLoaders = {
        ".toml": tomllib.load,
        ".json": json.load,
        ".txt": txt,
    }

    with resolved_path.open("rb") as f:
        data = loaders[resolved_path.suffix](f)

    if not isinstance(data, dict):
        raise ParseError(
            f"Inventory file '{path}' must contain a top-level object, "
            + f"got {type(data).__name__}"
        )

    preprocessed_data = preprocess(data)

    resolved_data = resolve_imports(
        preprocessed_data,
        loaders,
        path.parent,
        current_seen,
    )

    extends = resolved_data.pop("extends", [])
    match extends:
        case str():
            extends = [extends]
        case list():
            pass
        case _:
            raise ValueError(f"unexpected type {type(extends)}")

    registry = cast(DictRegistry, resolved_data)

    for extend_path in extends:
        if not isinstance(extend_path, str):
            raise ParseError(f"'extends' entries must be strings, got {extend_path!r}")

        extend_dict = _from_file(path.parent / extend_path, current_seen)
        registry = extend_registries(registry, extend_dict)

    return registry


def preprocess(raw_data: dict[str, Any]) -> dict[str, Any]:
    """Add exceptions before any processing"""

    data = deepcopy(raw_data)

    cases = data.get("case", {})
    for case, case_data in cases.items():
        if "payload" not in case_data:
            case_data.setdefault("payload_path", f"cases/{case}.txt")

        if isinstance(case_data["expects"], dict):
            expects = list(case_data["expects"].items())
            case_data["expects"] = []
            data.setdefault("expect", {})

            for scorer, payload in expects:
                expect_name = f"{case}|{scorer}"
                data["expect"][expect_name] = {
                    "scorer": scorer,
                    "payload": payload,
                }
                case_data["expects"].append(expect_name)

    return data


def extend_registries(base: DictRegistry, update: DictRegistry):
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
        new_obj: dict[str, Any] = {}

        for key, value in obj.items():
            if key.endswith("_path"):
                if not isinstance(value, str):
                    raise ParseError(
                        f"*_path is expected to be a string, was '{value}'"
                    )

                key = key.replace("_path", "")

                if key in obj:
                    raise ParseError(
                        f"Both '{key}_path' and '{key}' are defined, pick one. '{obj}'"
                    )

                path = (base_path / value).resolve()

                if path in seen:
                    loop = " -> ".join([p.name for p in seen] + [path.name])
                    raise ParseError(
                        f"Circular dependency detected in 'extends': {loop}"
                    )

                with path.open("rb") as f:
                    value = loaders[path.suffix](f)

                new_obj[key] = resolve_imports(
                    value,
                    loaders,
                    path.parent,
                    seen + [path],
                )
            else:
                new_obj[key] = resolve_imports(
                    value,
                    loaders,
                    base_path,
                    seen,
                )
        return new_obj

    elif isinstance(obj, list):
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
