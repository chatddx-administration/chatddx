from collections.abc import Mapping
from typing import Annotated, Any

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

# What a run returns when its output type's definition names no type: the
# model's text, as it wrote it. An empty definition is how an inventory or a
# form says "free text", so this is the output of most agents.
TEXT_SCHEMA: dict[str, JsonValue] = {"type": "string"}


def is_free_text(definition: Mapping[str, Any]) -> bool:
    """
    Whether a definition asks for the model's text rather than a value it
    describes: it names no type.
    """
    return definition.get("type") is None


def output_schema(definition: Mapping[str, Any]) -> dict[str, JsonValue]:
    """
    The JSON Schema of the value a run with this definition returns.

    A definition that names a type is that schema; one that does not stands
    for free text. The runtime builds an output from this and a scorer asks
    it whether it can read one, so neither decides on its own what an empty
    definition means.

    It describes the output, not how the model is made to produce it: the
    coercion strategy changes what goes over the wire, never this.
    """
    if is_free_text(definition):
        return dict(TEXT_SCHEMA)

    return dict(definition)


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
