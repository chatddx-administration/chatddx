# pyright: basic
import logging
from typing import Any

from pydantic import ValidationError
from rich import print
from rich.pretty import pretty_repr


def resolve_weirdos(val: Any):
    if hasattr(val, "__dict__") or "DjangoGetter" in type(val).__name__:
        return val.__dict__
    return val


"""
# --- Usage Example ---
    try:
        ...
    except ValidationError as e:
        if settings.MODE == "dev":
            from rich import print
            from chatddx.dx.error_handling import format_pydantic_errors
            print(format_pydantic_errors(e))

        raise e
"""


def print_pydantic_errors(
    exc: ValidationError,
    logger: logging.Logger | None = None,
) -> None:
    raw_errors = exc.errors()
    formatted_errors = []

    for err in raw_errors:
        err_copy = dict(err)

        if "input" in err_copy:
            err_copy["input"] = resolve_weirdos(err_copy["input"])

        err_copy["msg"] = f"Custom Notice: {err_copy['msg']}"

        formatted_errors.append(err_copy)

    if logger is None:
        print(formatted_errors)
    else:
        logger.warning(pretty_repr(formatted_errors, indent_size=4))

    for err in exc.errors():
        loc = " -> ".join(str(e) for e in err["loc"])
        print(f"{loc}: {err['msg']}\n")
