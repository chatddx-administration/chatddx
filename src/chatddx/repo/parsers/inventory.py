"""
The inventory parser: TOML files in, each entity's records out, as the trail
schema of their content and the details their branch carries.

An inventory file holds a table per entity, and each holds named records.
An author writes one record per entity, and the entity's bundle decides
which of its keys are content and which are details (datamodel.md §1).
A key that is neither is an error, and so is a record that names itself or
its owner: its name is its key, and its owner is whoever parses it.

- `extends` at the top of a file names the files it builds on. Its own
  records win over theirs, and the first file it names over the next.
- `extends` in a record names records of the same entity it builds on. Its
  own keys win, and the first record it names over the next. A table it sets
  replaces the one it would inherit: records are merged key by key, and no
  deeper.
- `partial = true` makes a record a template to extend, never a record of
  its own: it is left out, and it can't be named by a relation.
- `<key>_path` reads the key's value from a file next to the file that
  names it: TOML and JSON as data, anything `.txt` as text. Only a record's
  own keys read files; what they read is data.
- A relation names a record of the entity it points at: one name, or a list
  of names for a list. A record written inline would be committed without a
  name, and several names would merge into one nobody named, so neither is
  accepted.
- A case with no vignette reads it from `cases/<name>.txt` next to its file.
"""

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
    # as written, with what its `_path` keys name read in
    values: dict[str, Any]
    # the file it is written in, and how an error names that file
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
    """
    Every record of the inventory at `path` that isn't partial, as its trail
    and its branch's details. `branch_details` is what every branch carries
    whatever its record says, such as the owner.
    """
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
        """
        The record's values with what it extends merged in, keywords left
        out: its own keys win, and the first record it names over the next.
        """
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
            # content first: a tool's `name` is the name the LLM sees
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
    """The fields of an entity's trail that point at other entities' trails."""
    relations: dict[str, Relation] = {}

    for field_name, field in entity_of(entity).trail_in.model_fields.items():
        annotation: Any = field.annotation

        # an optional relation: the trail it points at, or none
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


# -------------------------------------------------------------------- files


def _read_inventory(path: Path, chain: tuple[Path, ...], base: Path) -> Records:
    """
    The records of the inventory file at `path` and of every file it
    extends, its own winning over theirs.
    """
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
    """What a record's `_path` key names, read."""
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
