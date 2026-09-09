# src/chatddx/registry/main.py
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import (
    IO,
    Any,
    Callable,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import (
    BaseModel,
    JsonValue,
    ValidationError,
)

from chatddx.registry.schemas import (
    BaseRegistry,
    DictRegistry,
    ParseError,
    Record,
)

FileLoaders = dict[str, Callable[[IO[bytes]], JsonValue]]


@dataclass
class InstanceValidationContext:
    get_record: Callable[[type[BaseModel], InstanceValidationContext], Record]
    data: DictRegistry
    schema: type[BaseRegistry]


def get_record_from_context(
    schema_class: type[BaseModel],
    context: InstanceValidationContext,
):
    bundle = None

    resolved_hints = get_type_hints(context.schema)

    for field_name, field_type in resolved_hints.items():
        if get_origin(field_type) is dict:
            args = get_args(field_type)
            if len(args) == 2 and args[0] is str and args[1] is schema_class:
                bundle = field_name
                break

    if bundle is None:
        raise TypeError(
            f"Could not find a field of type dict[str, {schema_class.__name__}] in schema '{context.schema.__name__}'"
        )

    try:
        return context.data[bundle]
    except KeyError:
        raise KeyError(f"bundle '{bundle}' has no data")


def parse_registry[T: BaseRegistry](
    path: Path,
    schema: type[T],
    patch: dict[str, Any] | None = None,
) -> T:
    cleaned_data: dict[str, Any] = {}
    data = _from_file(path)

    if patch is None:
        patch = {}

    for bundle, record in data.items():
        cleaned_data[bundle] = {}

        for field, instance in record.items():
            if isinstance(instance, dict) and instance.get("partial"):
                continue

            cleaned_data[bundle][field] = {"name": field} | instance | patch
    try:
        return schema.model_validate(
            cleaned_data,
            context=InstanceValidationContext(
                get_record=get_record_from_context,
                schema=schema,
                data=data,
            ),
        )
    except ValidationError as e:
        for err in e.errors():
            loc = " -> ".join(str(e) for e in err["loc"])
            print(f"{loc}: {err['msg']} (got {err.get('input')!r})")
        raise


def _from_file(
    path: Path,
    seen: list[Path] | None = None,
) -> DictRegistry:
    if seen is None:
        seen = list()

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

    with path.open("rb") as f:
        data = resolve_imports(
            loaders[path.suffix](f), loaders, path.parent, current_seen
        )

    if not isinstance(data, dict):
        raise ParseError(
            f"Registry file '{path}' must contain a top-level object, "
            f"got {type(data).__name__}"
        )

    extends = data.pop("extends", [])
    match extends:
        case str():
            extends = [extends]
        case list():
            pass
        case _:
            raise ValueError(f"unexpected type {type(extends)}")

    # Every remaining top-level value is a bundle of records; `extends` (a
    # path or list of paths, handled above) was the only other shape a
    # registry file's top level is allowed to carry.
    registry = cast(DictRegistry, data)

    for extend_path in extends:
        if not isinstance(extend_path, str):
            raise ParseError(f"'extends' entries must be strings, got {extend_path!r}")

        extend_dict = _from_file(path.parent / extend_path, current_seen)
        registry = extend_registries(registry, extend_dict)

    return registry


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
        seen = list()

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
