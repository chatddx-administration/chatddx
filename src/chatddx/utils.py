import asyncio
import hashlib
import inspect
import json
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import (
    Any,
    TypeGuard,
    cast,
    get_args,
    get_type_hints,
)

from asgiref.sync import sync_to_async
from django.db.models import Model as DjangoModel, QuerySet
from django.utils.html import format_html
from pydantic import BaseModel, Field, HttpUrl, JsonValue, create_model

type Observer[T] = Callable[[T], None | Awaitable[None]]

from typing import Annotated


def is_str_list(value: object) -> TypeGuard[list[str]]:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)  # pyright: ignore[reportUnknownVariableType]


def dig(data: Any, *path: str) -> Any:
    """Safely traverse nested dicts/objects without type checker noise."""
    for key in path:
        if not isinstance(data, dict):
            return None
        data = cast(dict[str, Any], data.get(key))
    return data


def make_fields_optional(model_cls: type[BaseModel]) -> type[BaseModel]:
    new_fields = {}
    for f_name, f_info in model_cls.model_fields.items():
        f_dct = f_info.asdict()
        new_fields[f_name] = (
            Annotated[
                f_dct["annotation"] | None,  # ruff: ignore[F821]
                *f_dct["metadata"],
                Field(**f_dct["attributes"]),
            ],
            None,
        )
    return create_model(
        f"{model_cls.__name__}Optional",
        __base__=model_cls,
        **new_fields,  # pyright: ignore[reportUnknownArgumentType]
    )


def make_async[**P, R](func: Callable[P, R]) -> Callable[P, Coroutine[None, None, R]]:
    return sync_to_async(func)


def is_target_in_annotation(annotation: type, target_schema: type[BaseModel]) -> bool:
    if annotation == target_schema:
        return True

    if issubclass(annotation, target_schema):
        return True

    args = get_args(annotation)
    for arg in args:
        if is_target_in_annotation(arg, target_schema):
            return True

    return False


@dataclass
class OneOf[T]:
    value: T


@dataclass
class ListOf[T]:
    values: list[T]


def default_parser(obj: Any):
    match obj:
        case Decimal():
            return str(obj)
        case HttpUrl():
            return str(obj)
        case _:
            raise TypeError(f"Unsupported type: {type(obj)}")


def generate_fingerprint(data: Mapping[str, JsonValue]):
    import orjson

    json = orjson.dumps(
        data,
        option=orjson.OPT_SORT_KEYS,
        default=default_parser,
    )

    return hashlib.sha256(json).hexdigest()


def one_or_list_of[T](t: type[T], value: object) -> OneOf[T] | ListOf[T] | None:
    if isinstance(value, t):
        return OneOf(value)

    if isinstance(value, list) and (not value or all(isinstance(x, t) for x in value)):  # pyright: ignore[reportUnknownVariableType]
        return ListOf(cast(list[T], value))


class Dispatcher:
    def __init__(self):
        self._handlers: dict[type[Any], list[Observer[Any]]] = {}

    def subscribe[T](self, fn: Observer[T]) -> Observer[T]:
        target = fn if inspect.isroutine(fn) else fn.__call__

        hints = get_type_hints(target)
        sig = inspect.signature(target)
        params = list(sig.parameters.values())

        name = getattr(fn, "__name__", type(fn).__name__)
        if not params:
            raise ValueError(f"Handler {name} must accept an argument.")

        first_arg_name = params[0].name
        item_type = hints.get(first_arg_name)

        if not item_type:
            raise TypeError(
                f"Missing type hint for '{first_arg_name}' in {fn.__name__}"
            )

        self._handlers.setdefault(item_type, []).append(fn)
        return fn

    async def publish(self, data: Any):
        tasks: list[Awaitable[Any]] = []
        for registered_type, handlers in self._handlers.items():
            if registered_type == Any or isinstance(data, registered_type):
                for handler in handlers:
                    if inspect.iscoroutinefunction(handler):
                        tasks.append(handler(data))
                    else:
                        tasks.append(asyncio.to_thread(handler, data))
        _ = await asyncio.gather(*tasks)


@dataclass
class StepNavItem:
    pk: int | None = None
    text: str | None = None


@dataclass
class StepNav:
    next_: StepNavItem = field(default_factory=StepNavItem)
    prev_: StepNavItem = field(default_factory=StepNavItem)


def get_step_nav(
    model: DjangoModel,
    qs: QuerySet[DjangoModel],
) -> StepNav:

    pks = list(qs.order_by("id").values_list("pk", flat=True))

    step_nav = StepNav()
    pk_index = pks.index(model.pk)

    step_nav.prev_.pk = pks[pk_index - 1] if pk_index > 0 else None
    step_nav.next_.pk = pks[pk_index + 1] if pk_index < len(pks) - 1 else None

    if step_nav.prev_.pk:
        prev_model = qs.get(pk=step_nav.prev_.pk)
        step_nav.prev_.text = str(prev_model)

    if step_nav.next_.pk:
        next_model = qs.get(pk=step_nav.next_.pk)
        step_nav.next_.text = str(next_model)

    return step_nav


def truncate_content(content: str | None, limit: int):
    if content is None:
        return ""
    if len(content) > limit:
        return content[:limit] + " (...)"
    return content


def render_json_html(data: Any) -> str:
    if data is None:
        return ""

    json_data = json.dumps(data, indent=4)
    return format_html(
        '<div class="highlight">'
        + '<pre class="white-space: pre-wrap; word-wrap: break-word;; line-height: 125%;">{}</pre>'
        + "</div>",
        json_data,
    )
