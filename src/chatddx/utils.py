from typing import Any, TypeGuard, cast


def is_str_list(value: object) -> TypeGuard[list[str]]:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)  # pyright: ignore[reportUnknownVariableType]


def dig(data: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(data, dict):
            return None
        data = cast(dict[str, Any], data.get(key))
    return data
