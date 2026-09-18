from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, HttpUrl, JsonValue

from chatddx.core.choices import ProviderChoices
from chatddx.core.fields import CoercedStr, TomlString, parse_toml_or_dict
from chatddx.repo.families import (
    BaseFormDataIn,
    BaseFormDataOut,
    BranchSchema,
    BranchSpec,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)
from chatddx.repo.families.pydantic import BaseTrail


class ConnectionBasePrimitives(BaseModel):
    provider: ProviderChoices
    model: str
    endpoint: HttpUrl


class ConnectionTrailBase(ConnectionBasePrimitives, BaseTrail):
    profile: dict[str, JsonValue] = Field(default_factory=dict)


class ConnectionTrailSchema(ConnectionTrailBase, TrailSchema):
    pass


class ConnectionTrailSchemaRef(
    TrailSchemaRef,
    ConnectionTrailBase,
):
    pass


class ConnectionTrailSpec(ConnectionTrailBase, TrailSpec):
    pass


class ConnectionBranchSchema(BranchSchema[ConnectionTrailSchema]):
    pass


class ConnectionBranchSpec(BranchSpec[ConnectionTrailSpec]):
    pass


class ConnectionFormDataIn(ConnectionTrailBase, BaseFormDataIn):
    profile: Annotated[
        dict[str, JsonValue],
        BeforeValidator(parse_toml_or_dict),
    ] = Field(default_factory=dict)


class ConnectionFormDataOut(ConnectionBasePrimitives, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    profile: TomlString
