from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, ClassVar

from ninja import Schema as NinjaSchema
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    computed_field,
)
from pydantic.fields import FieldInfo

from chatddx.core.fields import CoercedStr, NullableStr
from chatddx.core.schemas import IdentitySchemaOut
from chatddx.repo.families.canonical import fingerprint, ordered

ORDERED = "ordered"

RELATION = "relation"


def _marked(field: FieldInfo, marker: str) -> Any:
    extra = field.json_schema_extra
    return extra.get(marker) if isinstance(extra, dict) else None


class BaseTrail(BaseModel):
    pass


class TrailIn(BaseTrail):
    @computed_field
    @property
    def fingerprint(self) -> str:
        return fingerprint(self.canonical_input())

    def canonical_input(self) -> dict[str, Any]:
        relations: dict[str, Any] = {}

        # sibling in src/chatddx/repo/store/trail.py
        for field_name, value in self:
            match value:
                case TrailIn():
                    relations[field_name] = value.fingerprint

                case [*items] if items and all(
                    isinstance(item, TrailIn) for item in items
                ):
                    relations[field_name] = [item.fingerprint for item in items]

                case _:
                    pass

        data = self.model_dump(
            mode="json",
            exclude={"fingerprint", *relations},
        )

        for field_name, field in type(self).model_fields.items():
            if _marked(field, ORDERED) and field_name in data:
                data[field_name] = ordered(data[field_name])

        return data | relations


class TrailRef(BaseTrail):
    fingerprint: str


class TrailOut(BaseTrail, NinjaSchema):
    id: int
    fingerprint: str
    timestamp: datetime


class BaseBranchTrail[T: BaseTrail](BaseModel):
    trail: T


def relation_fields(details: type[BaseModel]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []

    for field_name, field in details.model_fields.items():
        resolver = _marked(field, RELATION)

        if resolver is not None:
            fields.append((field_name, str(resolver)))

    return fields


def plain_detail_fields(details: type[BaseModel]) -> list[str]:
    relations = {field_name for field_name, _ in relation_fields(details)}

    return [
        field_name
        for field_name in details.model_fields
        if field_name not in BRANCH_FIELDS and field_name not in relations
    ]


def dump_details(details: BaseModel) -> dict[str, JsonValue]:
    """The plain details of `details`, as the branch's `details` column holds them."""
    return details.model_dump(
        mode="json",
        include=set(plain_detail_fields(type(details))),
    )


class Details(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class BranchDetails(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    name: str
    owner: str

    collaborators: list[str] | None = Field(
        default=None,
        json_schema_extra={RELATION: "identity"},
    )
    tags: list[str] | None = Field(
        default=None,
        json_schema_extra={RELATION: "tag"},
    )


BRANCH_FIELDS = frozenset({"name", "owner"})


class BranchDetailsPatch(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    name: str | None = None
    owner: str | None = None

    collaborators: list[str] | None = Field(
        default=None,
        json_schema_extra={RELATION: "identity"},
    )
    tags: list[str] | None = Field(
        default=None,
        json_schema_extra={RELATION: "tag"},
    )


class BaseBranch[T: BaseTrail](BaseBranchTrail[T]):
    pass


class BranchIn[T: TrailIn](BaseBranch[T], BranchDetails):
    pass


class BranchOut[T: TrailOut, D: Details](BaseBranch[T], NinjaSchema):
    id: int
    name: str
    owner: IdentitySchemaOut
    timestamp: datetime

    collaborators: list[IdentitySchemaOut]
    tags: list[Annotated[str, BeforeValidator(str)]]

    details: D


class BaseFormDataIn(NinjaSchema):
    name: NullableStr = None
    owner: IdentitySchemaOut | None = None

    collaborators: list[IdentitySchemaOut] | None = None
    tags: list[Annotated[str, BeforeValidator(str)]] | None = None


class BaseFormDataOut(BaseModel):
    id: CoercedStr
    name: str = ""


_ = TrailIn.model_rebuild()
