from typing import Annotated, Any

from pydantic import BeforeValidator


def str_or_int(v: Any) -> str | Any:
    if isinstance(v, dict) and "id" in v:
        return str(v["id"])  # pyright: ignore[reportUnknownArgumentType]
    if isinstance(v, int):
        return str(v)
    return v  # pyright: ignore[reportUnknownVariableType]


def empty_str_to_none(v: Any):
    if v == "":
        return None
    return v


CoercedStr = Annotated[str, BeforeValidator(str_or_int)]


NullableStr = Annotated[str | None, BeforeValidator(empty_str_to_none)]
