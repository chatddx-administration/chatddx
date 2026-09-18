# src/chatddx/repo/tests/identity_boundary.py
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional, cast  # pyright: ignore[reportDeprecated]

from django.db.models import (
    BooleanField,
    CharField,
    DecimalField,
    IntegerField,
    JSONField,
    PositiveIntegerField,
    TextField,
    URLField,
)
from pydantic import HttpUrl, JsonValue

from chatddx.core.choices import (
    CoercionChoices,
    ProviderChoices,
    ToolChoices,
    ValidationChoices,
)
from chatddx.core.decimals import SamplingDecimal, SamplingDecimalBase
from chatddx.core.django_fields import JSONSchemaField
from chatddx.repo.entities.connection.django import ConnectionTrailModel
from chatddx.repo.entities.connection.pydantic import ConnectionTrailSchema
from chatddx.repo.entities.expect.django import ExpectTrailModel
from chatddx.repo.entities.expect.pydantic import ExpectTrailSchema
from chatddx.repo.entities.output_type.django import OutputTypeTrailModel
from chatddx.repo.entities.output_type.pydantic import OutputTypeTrailSchema
from chatddx.repo.entities.sampling_params.django import SamplingParamsTrailModel
from chatddx.repo.entities.sampling_params.pydantic import SamplingParamsTrailSchema
from chatddx.repo.entities.scorer.django import ScorerTrailModel
from chatddx.repo.entities.scorer.pydantic import ScorerTrailSchema
from chatddx.repo.entities.tool.django import ToolTrailModel
from chatddx.repo.entities.tool.pydantic import ToolTrailSchema
from chatddx.repo.entities.tool_group.django import ToolGroupTrailModel
from chatddx.repo.entities.tool_group.pydantic import ToolGroupTrailSchema
from chatddx.repo.inventories import InventoryTrailSchema
from chatddx.repo.parsers.inventory import parse
from chatddx.repo.shufflers import inventory

some_inventory: InventoryTrailSchema = inventory.trail_schema(
    parse(Path(__file__).parent / "../../data/test/some.toml")
)


def _test_Expects(value: list[ExpectTrailSchema]):
    expect = next(v for v in _test_optional_Expect(None) if v)
    if len(value) == 0:
        return value, [expect]
    if len(value) == 1:
        _, altered_expect = _test_Expect(value[0])
        return value, [altered_expect]
    return deepcopy(value), value[:1]


def _test_Expect(value: ExpectTrailSchema):
    altered_value = value.model_copy(
        update={
            "payload": _test_str(value.payload)[1],
        }
    )
    return deepcopy(value), altered_value


def _test_optional_Expect(value: ExpectTrailSchema | None):
    altered_value = some_inventory.expect["some-expect"] if value is None else None
    return deepcopy(value), altered_value


def _test_Scorer(value: ScorerTrailSchema):
    altered_value = value.model_copy(update={"command": _test_str(value.command)[1]})
    return deepcopy(value), altered_value


def _test_ToolGroup(value: ToolGroupTrailSchema):
    altered_value = value.model_copy(update={"tools": _test_tools(value.tools)[1]})
    return deepcopy(value), altered_value


def _test_optional_ToolGroup(value: ToolGroupTrailSchema | None):
    altered_value = (
        some_inventory.tool_group["some-tool_group"] if value is None else None
    )
    return deepcopy(value), altered_value


def _test_OutputType(value: OutputTypeTrailSchema):
    altered_value = value.model_copy(
        update={"definition": _test_jsonschema(value.definition)[1]}
    )
    return deepcopy(value), altered_value


def _test_optional_OutputType(value: OutputTypeTrailSchema | None):
    altered_value = (
        some_inventory.output_type["some-output_type"] if value is None else None
    )
    return deepcopy(value), altered_value


def _test_SamplingParams(value: SamplingParamsTrailSchema):
    altered_value = value.model_copy(
        update={"temperature": _test_optional_decimal(value.temperature)[1]}
    )

    return deepcopy(value), altered_value


def _test_optional_SamplingParams(value: SamplingParamsTrailSchema | None):
    altered_value = (
        some_inventory.sampling_params["some-sampling_params"]
        if value is None
        else None
    )
    return deepcopy(value), altered_value


def _test_Connection(value: ConnectionTrailSchema):
    altered_value = value.model_copy(update={"endpoint": _test_url(value.endpoint)[1]})
    return deepcopy(value), altered_value


def _test_url(value: HttpUrl):
    altered_value = HttpUrl(str(value) + "a")
    return value, altered_value


def _test_optional_Connection(value: ConnectionTrailSchema | None):
    altered_value = (
        some_inventory.connection["some-connection"] if value is None else None
    )
    return deepcopy(value), altered_value


def _test_tools(value: list[ToolTrailSchema]):
    tool = next(v for v in _test_optional_tool(None) if v)
    if len(value) == 0:
        return value, [tool]
    if len(value) == 1:
        _, altered_tool = _test_tool(value[0])
        return value, [altered_tool]
    return deepcopy(value), value[:1]


def _test_optional_tools(value: list[ToolTrailSchema] | None):
    altered_value = cast(list[ToolTrailSchema], []) if value is None else None
    return deepcopy(value), altered_value


def _test_tool(value: ToolTrailSchema):
    altered_value = value.model_copy(
        update={
            "description": _test_str(value.description)[1],
        }
    )
    return deepcopy(value), altered_value


def _test_optional_tool(value: ToolTrailSchema | None):
    altered_value = some_inventory.tool["some-tool"] if value is None else None
    return deepcopy(value), altered_value


def _test_dict_str_decimal(value: dict[str, SamplingDecimal]):
    return deepcopy(value), value | {"_": _test_optional_decimal(None)[1]}


def _test_jsonschema(value: dict[str, JsonValue]):
    altered_value = value | {
        "additionalProperties": _test_bool(
            cast(bool, value.get("additionalProperties", False))
        )[1]
    }

    return deepcopy(value), altered_value


def _test_optional_jsonschema(value: dict[str, JsonValue] | None):
    altered_value = cast(dict[str, JsonValue], {}) if value is None else None
    return deepcopy(value), altered_value


def _test_dict_str_any(value: dict[str, JsonValue]):
    return deepcopy(value), value | {"_": "'"}


def _test_optional_dict_str_any(value: dict[str, JsonValue] | None):
    altered_value = cast(dict[str, JsonValue], {}) if value is None else None
    return deepcopy(value), altered_value


def _test_list_str(value: list[str]):
    if len(value) == 0:
        return value, [_test_optional_str(None)[1]]
    if len(value) == 1:
        return value, _test_str(value[0])[1]

    return deepcopy(value), list(reversed(value))


def _test_optional_list_str(value: list[str] | None):
    altered_value = cast(list[str], []) if value is None else None
    return deepcopy(value), altered_value


def _test_provider_type(value: ProviderChoices):
    altered_value = next(v for v in ProviderChoices if v != value)
    return value, altered_value


def _test_tool_type(value: ToolChoices):
    altered_value = next(v for v in ToolChoices if v != value)
    return value, altered_value


def _test_validation_strategy(value: ValidationChoices):
    altered_value = next(v for v in ValidationChoices if v != value)
    return value, altered_value


def _test_coercion_strategy(value: CoercionChoices):
    altered_value = next(v for v in CoercionChoices if v != value)
    return value, altered_value


def _test_int(value: int):
    altered_value = 0 if value else 1
    return value, altered_value


def _test_optional_int(value: int | None):
    altered_value = 0 if value is None else None
    return value, altered_value


def _test_decimal(value: SamplingDecimal):
    # SamplingDecimal is an Annotated alias, not a callable class; construct
    # instances via its underlying concrete type instead.
    altered_value = SamplingDecimalBase(0) if value else SamplingDecimalBase("0.1")
    return value, altered_value


def _test_optional_decimal(value: SamplingDecimal | None):
    altered_value = SamplingDecimalBase(0) if value is None else None
    return value, altered_value


def _test_str(value: str):
    altered_value = "" if value else "'"
    return value, altered_value


def _test_optional_str(value: str | None):
    altered_value = "" if value is None else None
    return value, altered_value


def _test_bool(value: bool):
    return value, not value


field_types: dict[Any, Callable[[Any], tuple[Any, Any]]] = {
    (BooleanField, bool): _test_bool,
    (CharField, str): _test_str,
    (CharField, str | None): _test_optional_str,
    (CharField, ProviderChoices): _test_provider_type,
    (CharField, ToolChoices): _test_tool_type,
    (CharField, ValidationChoices): _test_validation_strategy,
    (CharField, CoercionChoices): _test_coercion_strategy,
    (ConnectionTrailModel, ConnectionTrailSchema): _test_Connection,
    (ConnectionTrailModel, ConnectionTrailSchema | None): _test_optional_Connection,
    (DecimalField, SamplingDecimal): _test_decimal,
    (DecimalField, Optional[SamplingDecimal]): _test_optional_decimal,  # noqa: UP045 # pyright: ignore[reportDeprecated]
    (IntegerField, int): _test_int,
    (IntegerField, int | None): _test_optional_int,
    (JSONField, dict[str, SamplingDecimal]): _test_dict_str_decimal,
    (JSONField, dict[str, JsonValue] | None): _test_optional_dict_str_any,
    (JSONField, dict[str, JsonValue]): _test_dict_str_any,
    (JSONField, list[str] | None): _test_optional_list_str,
    (JSONField, list[str]): _test_list_str,
    (JSONSchemaField, dict[str, JsonValue] | None): _test_optional_jsonschema,
    (JSONSchemaField, dict[str, JsonValue]): _test_jsonschema,
    (OutputTypeTrailModel, OutputTypeTrailSchema): _test_OutputType,
    (OutputTypeTrailModel, OutputTypeTrailSchema | None): _test_optional_OutputType,
    (PositiveIntegerField, int): _test_int,
    (PositiveIntegerField, int | None): _test_optional_int,
    (SamplingParamsTrailModel, SamplingParamsTrailSchema): _test_SamplingParams,
    (
        SamplingParamsTrailModel,
        SamplingParamsTrailSchema | None,
    ): _test_optional_SamplingParams,
    (TextField, str): _test_str,
    (TextField, str | None): _test_optional_str,
    (ToolTrailModel, list[ToolTrailSchema]): _test_tools,
    (ToolTrailModel, list[ToolTrailSchema] | None): _test_optional_tools,
    (ToolGroupTrailModel, ToolGroupTrailSchema): _test_ToolGroup,
    (ToolGroupTrailModel, ToolGroupTrailSchema | None): _test_optional_ToolGroup,
    (ExpectTrailModel, list[ExpectTrailSchema]): _test_Expects,
    (ScorerTrailModel, ScorerTrailSchema): _test_Scorer,
    (URLField, HttpUrl): _test_url,
}
