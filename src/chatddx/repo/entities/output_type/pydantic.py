from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, JsonValue

from chatddx.core.choices import CoercionChoices, ValidationChoices
from chatddx.core.fields import (
    CoercedStr,
    TomlString,
    parse_toml_or_dict,
    validate_json_schema,
)
from chatddx.repo.families import (
    BranchSchema,
    BranchSpec,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)
from chatddx.repo.families.pydantic import BaseFormDataIn, BaseFormDataOut, BaseTrail


class OutputTypeBasePrimitives(BaseModel):
    output_retries: int = 1
    validation_strategy: ValidationChoices = ValidationChoices.INFORM
    coercion_strategy: CoercionChoices = CoercionChoices.NATIVE


class OutputTypeTrailBase(OutputTypeBasePrimitives, BaseTrail):
    definition: Annotated[
        dict[str, JsonValue],
        AfterValidator(validate_json_schema),
    ] = Field(default_factory=dict)


class OutputTypeTrailSchema(OutputTypeTrailBase, TrailSchema):
    pass


class OutputTypeTrailSchemaRef(
    TrailSchemaRef,
    OutputTypeTrailBase,
):
    pass


class OutputTypeTrailSpec(OutputTypeTrailBase, TrailSpec):
    pass


class OutputTypeBranchSchema(BranchSchema[OutputTypeTrailSchema]):
    pass


class OutputTypeBranchSpec(BranchSpec[OutputTypeTrailSpec]):
    pass


class OutputTypeFormDataIn(OutputTypeTrailBase, BaseFormDataIn):
    definition: Annotated[
        dict[str, JsonValue],
        BeforeValidator(parse_toml_or_dict),
    ] = Field(default_factory=dict)


class OutputTypeFormDataOut(OutputTypeBasePrimitives, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    definition: TomlString
