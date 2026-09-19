from __future__ import annotations

from datetime import datetime
from typing import Annotated

from ninja import Schema as NinjaSchema
from pydantic import (
    BaseModel,
    BeforeValidator,
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


class BranchSchemaDetails(BaseModel):
    name: str
    owner: str

    # What a branch carries besides its content, by name: who it is shared
    # with, how it is labelled, and -- for a case -- which expectations it
    # names. None means the new version inherits the set from the one it
    # supersedes, a list means exactly that set.
    collaborators: list[str] | None = None
    tags: list[str] | None = None
    expects: list[str] | None = None


class BranchDetailsPatch(BaseModel):
    name: str | None = None
    owner: str | None = None

    collaborators: list[str] | None = None
    tags: list[str] | None = None
    expects: list[str] | None = None


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
