from __future__ import annotations

import json
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import NoneType
from typing import IO, Any, cast, get_args, get_origin

from pydantic import JsonValue, ValidationError

from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import ENTITY_NAMES, EntityName
from chatddx.repo.families.pydantic import (
    BRANCH_FIELDS,
    BranchDetailsPatch,
    TrailIn,
)
from chatddx.repo.inventories import ParsedInventory
from chatddx.utils import is_str_list


class ParseError(Exception):
    pass


FileLoader = Callable[[IO[bytes]], JsonValue]


def _read_text(f: IO[bytes]) -> JsonValue:
    return f.read().decode("utf-8").rstrip("\n")


LOADERS: dict[str, FileLoader] = {
    ".toml": tomllib.load,
    ".json": json.load,
    ".txt": _read_text,
}

KEYWORDS = frozenset({"extends", "partial"})

PATH_SUFFIX = "_path"


@dataclass(frozen=True)
class Record:
    entity: EntityName
    name: str
    values: dict[str, Any]
    file: Path
    where: str

    @property
    def partial(self) -> bool:
        return bool(self.values.get("partial", False))

    @property
    def extends(self) -> list[str]:
        extends: str | list[str] = self.values.get("extends", [])
        return [extends] if isinstance(extends, str) else extends

    def error(self, problem: str) -> ParseError:
        return ParseError(f"{self.entity} '{self.name}': {problem} ({self.where})")


type Records = dict[EntityName, dict[str, Record]]


@dataclass(frozen=True)
class Relation:
    entity: EntityName
    many: bool


def parse(
    path: Path,
    branch_details: BranchDetailsPatch | None = None,
) -> ParsedInventory:
    records = _read_inventory(path.resolve(), (), path.resolve().parent)
    parser = _Parser(records, branch_details or BranchDetailsPatch())

    return ParsedInventory.model_validate(
        {
            entity: {
                name: parser.parse(entity, name)
                for name, record in records.get(entity, {}).items()
                if not record.partial
            }
            for entity in ENTITY_NAMES
        }
    )


class _Parser:
    def __init__(self, records: Records, branch_details: BranchDetailsPatch):
        self.records: Records = records
        self.patch: dict[str, Any] = branch_details.model_dump(exclude_none=True)
        self.parsed: dict[tuple[EntityName, str], tuple[Any, Any]] = {}

    def parse(
        self,
        entity: EntityName,
        name: str,
        referrer: Record | None = None,
    ) -> tuple[Any, Any]:
        record = self.lookup(entity, name, referrer)

        if referrer is not None and record.partial:
            raise referrer.error(
                f"{entity} '{name}' is partial: a template to extend, not a record"
            )

        key = (entity, name)

        if key not in self.parsed:
            self.parsed[key] = self._parse(record)

        return self.parsed[key]

    def lookup(
        self,
        entity: EntityName,
        name: str,
        referrer: Record | None = None,
    ) -> Record:
        try:
            return self.records[entity][name]
        except KeyError:
            if referrer is None:
                raise
            raise referrer.error(f"unknown {entity} '{name}'") from None

    def merged(self, record: Record, chain: tuple[str, ...] = ()) -> dict[str, Any]:
        chain = (*chain, record.name)
        values = {k: v for k, v in record.values.items() if k not in KEYWORDS}

        for name in record.extends:
            if name in chain:
                loop = " -> ".join((*chain[chain.index(name) :], name))
                raise ParseError(
                    f"{record.entity} '{name}' extends itself: {loop} ({record.where})"
                )

            parent = self.lookup(record.entity, name, record)
            values = self.merged(parent, chain) | values

        return values

    def _parse(self, record: Record) -> tuple[Any, Any]:
        bundle = entity_of(record.entity)
        content_keys = bundle.trail_in.model_fields
        detail_keys = set(bundle.branch_details_patch.model_fields) - BRANCH_FIELDS
        relations = _relations(record.entity)

        values = self.merged(record)

        if record.entity == "case" and "vignette" not in values:
            values["vignette"] = _load(
                record, record.file.parent / f"cases/{record.name}.txt"
            )

        content: dict[str, Any] = {}
        details: dict[str, Any] = {}

        for key, value in values.items():
            if key in content_keys:
                relation = relations.get(key)
                content[key] = (
                    value
                    if relation is None
                    else self.relate(record, key, value, relation)
                )
            elif key in BRANCH_FIELDS:
                raise record.error(
                    f"'{key}' can't be set: a record's name is its key, and its "
                    + "owner is whoever parses the inventory"
                )
            elif key in detail_keys:
                details[key] = value
            else:
                raise record.error(
                    f"unknown key '{key}': {record.entity} content is "
                    + f"{_listed(content_keys)}, and its details are "
                    + f"{_listed(detail_keys)}"
                )

        try:
            trail = bundle.trail_in.model_validate(content)
            branch_details = bundle.branch_details_patch.model_validate(
                details | {"name": record.name} | self.patch
            )
        except ValidationError as e:
            raise record.error(_problems(e)) from None

        return trail, branch_details

    def relate(self, record: Record, key: str, value: Any, relation: Relation) -> Any:
        if relation.many:
            if not is_str_list(value):
                raise record.error(
                    f"'{key}' names {relation.entity}s: a list of their names, "
                    + f"not {value!r}"
                )

            return [self.parse(relation.entity, name, record)[0] for name in value]

        if not isinstance(value, str):
            raise record.error(
                f"'{key}' names a {relation.entity}: one name, not {value!r}"
            )

        return self.parse(relation.entity, value, record)[0]


def _relations(entity: EntityName) -> dict[str, Relation]:
    relations: dict[str, Relation] = {}

    for field_name, field in entity_of(entity).trail_in.model_fields.items():
        annotation: Any = field.annotation

        if NoneType in get_args(annotation):
            options = [arg for arg in get_args(annotation) if arg is not NoneType]

            if len(options) != 1:
                continue

            annotation = options[0]

        many = get_origin(annotation) is list

        if many:
            annotation = get_args(annotation)[0]

        if isinstance(annotation, type) and issubclass(annotation, TrailIn):
            relations[field_name] = Relation(entity_of(annotation).name, many)

    return relations


def _problems(error: ValidationError) -> str:
    problems: list[str] = []

    for detail in error.errors():
        where = ".".join(str(part) for part in detail["loc"])
        message = detail["msg"].removeprefix("Value error, ")
        problems.append(f"{where}: {message}" if where else message)

    return "; ".join(problems)


def _listed(keys: Any) -> str:
    return ", ".join(sorted(keys)) or "nothing"


def _read_inventory(path: Path, chain: tuple[Path, ...], base: Path) -> Records:
    where = _relative(path, base)

    if path in chain:
        loop = " -> ".join(_relative(p, base) for p in (*chain, path))
        raise ParseError(f"{loop}: an inventory extends itself")

    data = _load_file(path, where)

    if not isinstance(data, dict):
        raise ParseError(f"{where}: an inventory is a table, not {type(data).__name__}")

    extends = data.pop("extends", [])
    paths = [extends] if isinstance(extends, str) else extends

    if not is_str_list(paths):
        raise ParseError(
            f"{where}: 'extends' is a path or a list of paths, not {extends!r}"
        )

    records: Records = {}

    for entity, table in data.items():
        if entity not in ENTITY_NAMES:
            raise ParseError(
                f"unknown entity '{entity}' ({where}); the entities are "
                + ", ".join(ENTITY_NAMES)
            )

        if not isinstance(table, dict):
            raise ParseError(
                f"'{entity}' is a table of named records, not "
                + f"{type(table).__name__} ({where})"
            )

        records[entity] = {
            name: _record(entity, name, values, path, where)
            for name, values in table.items()
        }

    for extended in paths:
        theirs = _read_inventory(
            (path.parent / extended).resolve(), (*chain, path), base
        )

        for entity, table in theirs.items():
            records[entity] = table | records.get(entity, {})

    return records


def _record(
    entity: EntityName,
    name: str,
    values: Any,
    file: Path,
    where: str,
) -> Record:
    if not isinstance(values, dict):
        raise ParseError(
            f"{entity} '{name}' must be a table, not {type(values).__name__} ({where})"
        )

    values = cast(dict[str, Any], values)
    record = Record(entity, name, {}, file, where)

    extends = values.get("extends", [])

    if not isinstance(extends, str) and not is_str_list(extends):
        raise record.error(f"'extends' is a name or a list of names, not {extends!r}")

    if not isinstance(values.get("partial", False), bool):
        raise record.error(f"'partial' is true or false, not {values['partial']!r}")

    read: dict[str, Any] = {}

    for key, value in values.items():
        if not key.endswith(PATH_SUFFIX) or key in KEYWORDS:
            read[key] = value
            continue

        target = key.removesuffix(PATH_SUFFIX)

        if target in values:
            raise record.error(f"both '{target}' and '{key}' are given, pick one")

        if not isinstance(value, str):
            raise record.error(f"'{key}' is a path, not {value!r}")

        read[target] = _load(record, file.parent / value)

    return Record(entity, name, read, file, where)


def _load(record: Record, path: Path) -> JsonValue:
    try:
        return _load_file(path, _relative(path, record.file.parent))
    except ParseError as e:
        raise record.error(str(e)) from None


def _load_file(path: Path, where: str) -> JsonValue:
    try:
        loader = LOADERS[path.suffix]
    except KeyError:
        raise ParseError(f"no loader for '{path.suffix}' files: {where}") from None

    try:
        with path.open("rb") as f:
            return loader(f)
    except FileNotFoundError:
        raise ParseError(f"no such file: {where}") from None
    except (tomllib.TOMLDecodeError, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ParseError(f"{where}: {e}") from None


def _relative(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)
