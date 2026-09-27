from ninja import Schema as NinjaSchema
from pydantic import BaseModel, Field, JsonValue


class IdentityBase(BaseModel):
    name: str
    secrets: dict[str, JsonValue] = Field(default_factory=dict)


class IdentitySchemaOut(IdentityBase, NinjaSchema):
    id: int
    secrets: dict[str, JsonValue] = Field(default_factory=dict, exclude=True)
