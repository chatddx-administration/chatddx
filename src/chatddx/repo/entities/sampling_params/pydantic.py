from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, JsonValue

from chatddx.core.decimals import SamplingDecimal
from chatddx.core.fields import (
    CoercedStr,
    TextListSimple,
    TomlString,
    parse_text_or_list,
    parse_toml_or_dict,
)
from chatddx.repo.families import (
    BranchSchema,
    BranchSpec,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)
from chatddx.repo.families.pydantic import BaseFormDataIn, BaseFormDataOut, BaseTrail


class SamplingParamsBasePrimitives(BaseModel):
    temperature: SamplingDecimal | None = None
    top_p: SamplingDecimal | None = None
    top_k: int | None = None
    max_tokens: int | None = None
    seed: int | None = None
    n: int | None = None
    presence_penalty: SamplingDecimal | None = None
    frequency_penalty: SamplingDecimal | None = None


class SamplingParamsTrailBase(SamplingParamsBasePrimitives, BaseTrail):
    stop_sequences: list[str] = Field(default_factory=list)
    logit_bias: dict[str, SamplingDecimal] = Field(default_factory=dict)
    provider_params: dict[str, JsonValue] = Field(default_factory=dict)


class SamplingParamsTrailSchema(SamplingParamsTrailBase, TrailSchema):
    pass


class SamplingParamsTrailSchemaRef(
    TrailSchemaRef,
    SamplingParamsTrailBase,
):
    pass


class SamplingParamsTrailSpec(SamplingParamsTrailBase, TrailSpec):
    pass


class SamplingParamsBranchSchema(BranchSchema[SamplingParamsTrailSchema]):
    pass


class SamplingParamsBranchSpec(BranchSpec[SamplingParamsTrailSpec]):
    pass


class SamplingParamsFormDataIn(SamplingParamsTrailBase, BaseFormDataIn):
    stop_sequences: Annotated[
        list[str],
        BeforeValidator(parse_text_or_list),
    ] = Field(default_factory=list)
    logit_bias: Annotated[
        dict[str, SamplingDecimal],
        BeforeValidator(parse_toml_or_dict),
    ] = Field(default_factory=dict)

    provider_params: Annotated[
        dict[str, JsonValue],
        BeforeValidator(parse_toml_or_dict),
    ] = Field(default_factory=dict)


class SamplingParamsFormDataOut(SamplingParamsBasePrimitives, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    logit_bias: TomlString
    provider_params: TomlString
    stop_sequences: TextListSimple
