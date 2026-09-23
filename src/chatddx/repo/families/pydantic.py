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

# Marks a field of a trail schema whose value keeps its order in the
# fingerprint: a JSON Schema, which a model reads, and a constrained decoder
# emits, in the order it is written. See `chatddx.repo.families.canonical`.
ORDERED = "ordered"

# Marks a field of a branch-details model as naming rows of another table
# rather than holding a value. The name is a key into
# `chatddx.repo.shufflers.branch.RELATION_RESOLVERS`, which turns each name
# into the row it stands for.
RELATION = "relation"


def _marked(field: FieldInfo, marker: str) -> Any:
    extra = field.json_schema_extra
    return extra.get(marker) if isinstance(extra, dict) else None


class BaseTrail(BaseModel):
    pass


class TrailSchema(BaseTrail):
    """
    An entity's content: everything authored that identifies it, and nothing
    else. Its fingerprint is what a trail row is deduplicated on.
    """

    @computed_field
    @property
    def fingerprint(self) -> str:
        return fingerprint(self.canonical_input())

    def canonical_input(self) -> dict[str, Any]:
        """
        What the fingerprint is a hash of: the fields in JSON form, with each
        relation standing in as its own fingerprint.
        """
        relations: dict[str, Any] = {}

        # sibling in src/chatddx/repo/shufflers/trail.py
        for field_name, value in self:
            match value:
                case TrailSchema():
                    relations[field_name] = value.fingerprint

                case [*items] if items and all(
                    isinstance(item, TrailSchema) for item in items
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


class TrailSchemaRef(BaseTrail):
    fingerprint: str


class TrailSpec(BaseTrail, NinjaSchema):
    id: int
    fingerprint: str
    timestamp: datetime


class BaseBranchTarget[T: BaseTrail](BaseModel):
    target: T


def relation_fields(details: type[BaseModel]) -> list[tuple[str, str]]:
    """
    The `(field_name, resolver_name)` pairs of a branch-details model, i.e.
    the rows of other tables this kind of branch carries beside its content.
    """
    fields: list[tuple[str, str]] = []

    for field_name, field in details.model_fields.items():
        resolver = _marked(field, RELATION)

        if resolver is not None:
            fields.append((field_name, str(resolver)))

    return fields


def plain_detail_fields(details: type[BaseModel]) -> list[str]:
    """
    The fields of a branch-details model that hold values of their own: not
    the branch's name or owner, and not a relation. They are what the branch's
    `details` column holds.
    """
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
    """
    What an entity's branch says about its content without being part of it:
    a machine's specs, a model's facts, a stack's endpoint. Details are never
    fingerprinted. They are the owner's, per branch, and a change to them
    makes a new version of the branch (new-datamodel.md §1).

    An entity with details subclasses this, and its branch details and their
    patch mix it in. The base is empty: most entities have none.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class BranchSchemaDetails(BaseModel):
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


# What every branch has as columns of its own rather than in `details`.
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


class BaseBranch[T: BaseTrail](BaseBranchTarget[T]):
    pass


class BranchSchema[T: TrailSchema](BaseBranch[T], BranchSchemaDetails):
    pass


class BranchSpec[T: TrailSpec, D: Details](BaseBranch[T], NinjaSchema):
    id: int
    name: str
    owner: IdentitySchemaOut
    timestamp: datetime

    collaborators: list[IdentitySchemaOut]
    tags: list[Annotated[str, BeforeValidator(str)]]

    # what the version says beside its content; see `Details`
    details: D


class BaseFormDataIn(NinjaSchema):
    name: NullableStr = None
    owner: IdentitySchemaOut | None = None

    # None where the form has no field for it, and so nothing to say about it
    collaborators: list[IdentitySchemaOut] | None = None
    tags: list[Annotated[str, BeforeValidator(str)]] | None = None


class BaseFormDataOut(BaseModel):
    id: CoercedStr
    name: str = ""


# Resolve trail's dependence on BaseBranchDetails
_ = TrailSchema.model_rebuild()
