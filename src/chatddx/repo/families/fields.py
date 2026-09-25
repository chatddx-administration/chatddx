import re
from collections.abc import Callable
from typing import Annotated

import jsonschema
from jsonschema.validators import validator_for
from pydantic import AfterValidator, JsonValue, StringConstraints

STORE_PATH = re.compile(r"/nix/store/[0-9a-df-np-sv-z]{32}-[^/]+")
_PINNED_SOURCE = re.compile(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}")


def _store_path(value: str) -> str:
    if not STORE_PATH.fullmatch(value):
        raise ValueError(
            f"{value!r} is not a Nix store path (/nix/store/<hash>-<name>)"
        )

    return value


def _pinned_source(value: str) -> str:
    if not _PINNED_SOURCE.fullmatch(value):
        raise ValueError(
            f"{value!r} is not a pinned source: write the repository and the "
            + "commit, as <owner>/<repository>@<40 hex digits>"
        )

    return value


def _json_schema(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    validator = validator_for(value, default=jsonschema.Draft202012Validator)

    try:
        validator.check_schema(value)
    except jsonschema.SchemaError as e:
        raise ValueError(f"not a valid JSON Schema: {e.message}") from None

    return value


def distinct[T](label: Callable[[T], object] = lambda item: item) -> AfterValidator:

    def check(items: list[T]) -> list[T]:
        seen: set[object] = set()

        for item in items:
            key = label(item)

            if key in seen:
                raise ValueError(f"{key!r} appears twice")

            seen.add(key)

        return items

    return AfterValidator(check)


# `/nix/store/<hash>-<name>`: the build, system or package a thing is
StorePath = Annotated[str, AfterValidator(_store_path)]

# `module.path:function`: a function in one of chatddx's own files, which the
# package it must be in holds to when it is loaded (`runtime.implementation`)
EntryPoint = Annotated[
    str, StringConstraints(pattern=r"^[\w.]+:[A-Za-z_][A-Za-z0-9_]*$")
]

# `<owner>/<repository>@<commit>`, as Hugging Face names a model's revision
PinnedSource = Annotated[str, AfterValidator(_pinned_source)]

JsonSchema = Annotated[dict[str, JsonValue], AfterValidator(_json_schema)]
