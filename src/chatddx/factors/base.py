import hashlib
import hmac
import json
import re
import types
import typing
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import (
    Annotated,
    Any,
    ClassVar,
    Literal,
    Self,
    cast,
    get_args,
    get_origin,
    override,
)

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    GetJsonSchemaHandler,
    JsonValue,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    StringConstraints,
    model_serializer,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Api = Literal["chat.completions"]


type Wording = str | tuple[str, str]
type Param = str | int | float


def _filled(wording: Wording, params: Mapping[str, Param]) -> str:
    english = wording if isinstance(wording, str) else wording[params["num"] != 1]
    return english % params


class Worded(Exception):
    wording: Wording | None = None
    params: Mapping[str, Param] = types.MappingProxyType({})

    @classmethod
    def of(cls, wording: Wording, /, **params: Param) -> Self:
        made = cls(_filled(wording, params))
        made.wording, made.params = wording, params
        return made

    @classmethod
    def raw(cls, english: str, /, **params: Param) -> Self:
        """Its English and parameters as `of` has them, unworded: what a person can't
        cause through the portal, which is passed on as it comes rather than said."""
        made = cls(_filled(english, params))
        made.params = params
        return made


class StructuralError(Worded, ValueError):
    pass


class Invalid(Worded, ValueError):
    pass


class Missing(Worded, LookupError):
    pass


def canonical_bytes(doc: JsonValue) -> bytes:
    return json.dumps(
        doc, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def sorted_keys[V](mapping: dict[str, V]) -> dict[str, V]:
    return dict(sorted(mapping.items()))


def display_names(names: Iterable[str]) -> str:
    return ", ".join(sorted(names))


LANGUAGE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{1,8})*$")


def language_tag(value: str) -> str:
    if not LANGUAGE.match(value):
        raise Invalid.of(
            "%(value)s is not a language tag such as 'sv' or 'pt-BR'", value=repr(value)
        )
    return value


type Language = Annotated[str, AfterValidator(language_tag)]


def distinct[T](values: tuple[T, ...]) -> tuple[T, ...]:
    if len(set(values)) != len(values):
        raise Invalid.of("duplicates are not allowed")
    return values


def ascending(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(values))


Settings = Annotated[dict[str, JsonValue], AfterValidator(sorted_keys)]


def sha256_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _holds_nul(node: JsonValue) -> bool:
    match node:
        case str():
            return "\0" in node
        case dict():
            return any("\0" in k or _holds_nul(v) for k, v in node.items())
        case list():
            return any(_holds_nul(v) for v in node)
        case _:
            return False


class Frozen(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    @model_serializer(mode="wrap")
    def _serialize(
        self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> Any:
        data = handler(self)
        context = cast(dict[str, object] | None, info.context)
        if not (context and context.get("canonical")):
            return data
        fields = cast(dict[str, object], data)
        for name, field in type(self).model_fields.items():
            if name in ("kind", "stage") or field.is_required():
                continue
            if getattr(self, name) == field.get_default(call_default_factory=True):
                _ = fields.pop(name, None)
        return sorted_keys(fields)


@dataclass(frozen=True, init=False)
class RefTo:
    kinds: tuple[str, ...]

    def __init__(self, *kinds: str) -> None:
        object.__setattr__(self, "kinds", kinds)

    def __get_pydantic_json_schema__(
        self, core: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        schema = handler(core)
        schema["x-kind"] = list(self.kinds)
        return schema


@dataclass(frozen=True)
class RefSite:
    path: str
    kinds: tuple[str, ...]
    digest: str


def iter_refs(model: BaseModel, prefix: str = "") -> Iterator[RefSite]:
    for name, field in type(model).model_fields.items():
        tp: Any = field.annotation
        if field.metadata:
            tp = Annotated[tp, *field.metadata]
        yield from _walk(tp, getattr(model, name), f"{prefix}/{name}")


def _walk(tp: Any, value: Any, path: str) -> Iterator[RefSite]:
    if value is None:
        return
    origin = get_origin(tp)
    if origin is Annotated:
        base, *meta = get_args(tp)
        for m in meta:
            if isinstance(m, RefTo):
                yield RefSite(path, m.kinds, value)
                return
        yield from _walk(base, value, path)
    elif isinstance(value, BaseModel):
        yield from iter_refs(value, path)
    elif origin is typing.Union or origin is types.UnionType:  # pyright: ignore[reportDeprecated]
        for arm in get_args(tp):
            found = list(_walk(arm, value, path))
            if found:
                yield from found
                return
    elif origin in (tuple, list, frozenset):
        elem = get_args(tp)[0]
        for i, v in enumerate(value):
            yield from _walk(elem, v, f"{path}/{i}")
    elif origin is dict:
        elem = get_args(tp)[1]
        for k, v in value.items():
            yield from _walk(elem, v, f"{path}/{k}")


Resolver = Callable[[str], "Component"]

type Upgrade = Callable[[dict[str, object]], dict[str, object]]


def upgraded(
    name: str, doc: dict[str, object], current: int, upgrades: Mapping[int, Upgrade]
) -> dict[str, object]:
    """The doc, its "v" popped, brought to `current` by `upgrades[v]`, which takes a
    doc of version v to v + 1, each in turn: as cheap as the upgrades. Raises a
    StructuralError for a version it has no way up from."""
    v = doc.pop("v", None)
    if not isinstance(v, int) or isinstance(v, bool) or v > current:
        raise StructuralError(f"{name} v{v} is not readable by v{current}")
    while v < current:
        upgrade = upgrades.get(v)
        if upgrade is None:
            raise StructuralError(f"{name} v{v} is not readable by v{current}")
        doc, v = upgrade(doc), v + 1
    return doc


class Component(Frozen):
    # Policy: bump when an existing field's meaning or default changes; additive fields
    # don't. A bump adds the upgrade from the version before to `upgrades`, so that
    # what is stored at it stays readable.
    schema_version: ClassVar[int] = 1
    upgrades: ClassVar[Mapping[int, Upgrade]] = {}

    @classmethod
    @override
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        field = cls.model_fields.get("kind")
        if field is not None and not isinstance(field.default, str):
            raise TypeError(f"{cls.__name__}.kind needs a literal default")

    # Accommodating for jsonb, which the store keeps each component as and which can't
    # hold U+0000 (src/chatddx/store/migrations/0001-t0-factor.sql).
    @model_validator(mode="after")
    def _storable(self) -> Self:
        if _holds_nul(self.canonical_doc()):
            raise Invalid.of("U+0000 can't be stored")
        return self

    @property
    def kind_name(self) -> str:
        kind = type(self).model_fields["kind"].default
        assert isinstance(kind, str)
        return kind

    def canonical_doc(self) -> dict[str, JsonValue]:
        doc = self.model_dump(mode="json", context={"canonical": True})
        return sorted_keys({**doc, "v": type(self).schema_version})

    @cached_property
    def canonical(self) -> bytes:
        return canonical_bytes(self.canonical_doc())

    @cached_property
    def digest(self) -> str:
        return sha256_digest(self.canonical)

    @override
    def model_copy(
        self, *, update: Mapping[str, Any] | None = None, deep: bool = False
    ) -> Self:
        copy = super().model_copy(deep=deep)
        if not update:
            return copy
        fields = {name: getattr(copy, name) for name in type(self).model_fields}
        return type(self).model_validate({**fields, **update})

    def refs(self) -> list[RefSite]:
        return list(iter_refs(self))

    def cross_check(self, get: Resolver) -> list[str]:  # pyright: ignore[reportUnusedParameter]
        return []


def resolve[C: Component](get: Resolver, digest: str, cls: type[C]) -> C:
    component = get(digest)
    if not isinstance(component, cls):
        raise StructuralError(
            f"{digest} is a {component.kind_name}, not a {cls.__name__}"
        )
    return component


class Fingerprint(Frozen):
    alg: Literal["sha256", "hmac-sha256"] = "sha256"
    key_id: str | None = None
    hex: Sha256Hex

    @model_validator(mode="after")
    def _key_id(self) -> "Fingerprint":
        if (self.alg == "hmac-sha256") != (self.key_id is not None):
            raise ValueError("key_id goes with hmac-sha256, and only with it")
        return self

    @classmethod
    def of(cls, data: bytes, key: tuple[str, bytes] | None = None) -> "Fingerprint":
        if key is None:
            return cls(hex=hashlib.sha256(data).hexdigest())
        key_id, secret = key
        return cls(
            alg="hmac-sha256",
            key_id=key_id,
            hex=hmac.new(secret, data, hashlib.sha256).hexdigest(),
        )


class Code(Frozen):
    distribution: str
    version: str
    revision: str | None = None


class Finding(Frozen):
    level: Literal["info", "warning"] = "warning"
    code: str
    message: str
    subject: str | None = None
    wording: Wording | None = None
    params: dict[str, Param] = Field(default_factory=dict[str, Param])

    @classmethod
    def of(
        cls,
        code: str,
        wording: Wording,
        /,
        *,
        level: Literal["info", "warning"] = "warning",
        subject: str | None = None,
        **params: Param,
    ) -> Self:
        return cls(
            level=level,
            code=code,
            message=_filled(wording, params),
            subject=subject,
            wording=wording,
            params=params,
        )

    @override
    def __hash__(self) -> int:
        return hash((self.level, self.code, self.message, self.subject))
