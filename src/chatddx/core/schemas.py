from uuid import UUID

from ninja import Schema as NinjaSchema
from pydantic import BaseModel, Field, JsonValue


class IdentityBase(BaseModel):
    name: str
    user_id: int | None = None
    guest_id: UUID | None = None
    secrets: dict[str, JsonValue] = Field(default_factory=dict)


class IdentitySchemaIn(IdentityBase):
    pass


class IdentitySchemaOut(IdentityBase, NinjaSchema):
    id: int
