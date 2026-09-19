from __future__ import annotations

from datetime import datetime
from typing import Annotated

from ninja import Schema as NinjaSchema
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    computed_field,
)

from chatddx.core.fields import CoercedStr, NullableStr
from chatddx.core.schemas import IdentitySchemaOut
from chatddx.utils import generate_fingerprint


class BaseTrail(BaseModel):
    pass


class TrailSchema(BaseTrail):
    @computed_field
    def fingerprint(self) -> str:
        return self.as_fingerprint()

    def as_fingerprint(self):
        relation_names: set[str] = set()
        relation_fingerprints = {}

        exclude = {"fingerprint"}

        for field_name, field_info in type(self).model_fields.items():
            val = getattr(self, field_name)
            extra = field_info.json_schema_extra or {}

            if extra.get("exclude_from_fingerprint"):
                exclude.add(field_name)
                continue

            # sibling in src/chatddx/repo/shufflers/trail.py
            match val:
                case TrailSchema():
                    relation_names.add(field_name)
                    relation_fingerprints[field_name] = val.as_fingerprint()

                case [*values] if any(
                    isinstance(value, TrailSchema) for value in values
                ):
                    relation_names.add(field_name)
                    relation_fingerprints[field_name] = [
                        item.as_fingerprint() if isinstance(item, TrailSchema) else item
                        for item in val
                    ]
                case _:
                    pass

        serialized = self.model_dump(exclude=exclude | relation_names)

        return generate_fingerprint(serialized | relation_fingerprints)


class TrailSchemaRef(BaseTrail):
    fingerprint: str


class TrailSpec(BaseTrail, NinjaSchema):
    id: int
    fingerprint: str
    timestamp: datetime


class BaseBranchTarget[T: BaseTrail](BaseModel):
    target: T


# Marks a field of a branch-details model as naming rows of another table
# rather than holding a value. The name is a key into
# `chatddx.repo.shufflers.branch.RELATION_RESOLVERS`, which turns each name
# into the row it stands for.
#
# sibling idiom in `TrailSchema.as_fingerprint` above
RELATION = "relation"


def relation_fields(details: type[BaseModel]) -> list[tuple[str, str]]:
    """
    The `(field_name, resolver_name)` pairs of a branch-details model, i.e.
    what this kind of branch carries beside its content.
    """
    fields: list[tuple[str, str]] = []

    for field_name, field_info in details.model_fields.items():
        extra = field_info.json_schema_extra

        if not isinstance(extra, dict):
            continue

        resolver = extra.get(RELATION)

        if resolver is not None:
            fields.append((field_name, str(resolver)))

    return fields


class BranchSchemaDetails(BaseModel):
    """
    What a branch carries besides its content, by name.

    Every entity has a name, an owner, collaborators and tags. An entity that
    carries more subclasses this and adds it, so that naming something an
    entity does not carry is an error rather than a silent no-op -- see
    `chatddx.repo.entities.case.pydantic.CaseBranchDetails`.

    For a relation field, None means the new version inherits the set from
    the one it supersedes, and a list means exactly that set.
    """

    model_config = ConfigDict(extra="forbid")

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


class BranchDetailsPatch(BaseModel):
    """
    `BranchSchemaDetails` with nothing required, for an inventory that names
    only some of what a branch carries. Its per-entity counterparts live
    beside the details model they patch.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    owner: str | None = None

    collaborators: list[str] | None = None
    tags: list[str] | None = None


class BaseBranch[T: BaseTrail](BaseBranchTarget[T]):
    pass


class BranchSchema[T: TrailSchema](BaseBranch[T], BranchSchemaDetails):
    pass


class BranchSpec[T: TrailSpec](BaseBranch[T], NinjaSchema):
    id: int
    name: str
    owner: IdentitySchemaOut
    timestamp: datetime

    collaborators: list[IdentitySchemaOut]
    tags: list[Annotated[str, BeforeValidator(str)]]


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
