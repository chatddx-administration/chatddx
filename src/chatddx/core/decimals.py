import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, override

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler, PlainSerializer
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

PRECISION = Decimal("0.01")

decimal_json_schema = {
    "type": "number",
    "description": "A decimal with sampling constraints",
}


class SamplingDecimalBase(Decimal):
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(cls._validate)

    @classmethod
    def _validate(cls, v: Any) -> "SamplingDecimal":
        return cls(Decimal(str(v)).quantize(PRECISION, rounding=ROUND_HALF_UP))

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: GetCoreSchemaHandler,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        return decimal_json_schema


SamplingDecimal = Annotated[
    SamplingDecimalBase, PlainSerializer(lambda v: float(v), return_type=float)
]


class DecimalEncoder(json.JSONEncoder):
    @override
    def default(self, o: Any):
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


class DecimalDecoder(json.JSONDecoder):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs, parse_float=Decimal)
