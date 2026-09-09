# src/chatddx/repo/main.py
from dataclasses import dataclass, fields
from typing import Any, Literal, TypedDict, TypeGuard, get_args

from chatddx.repo import proxies
from chatddx.repo.base import (
    BaseFormDataIn,
    BaseFormDataOut,
    BranchModel,
    BranchProxy,
    BranchSchema,
    BranchSpec,
    TrailModel,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)
from chatddx.repo.branch_models import (
    AgentBranchModel,
    CaseBranchModel,
    ConnectionBranchModel,
    OutputTypeBranchModel,
    SamplingParamsBranchModel,
    ToolBranchModel,
    ToolGroupBranchModel,
)
from chatddx.repo.branch_spec import (
    AgentBranchSpec,
    CaseBranchSpec,
    ConnectionBranchSpec,
    OutputTypeBranchSpec,
    SamplingParamsBranchSpec,
    ToolBranchSpec,
    ToolGroupBranchSpec,
)
from chatddx.repo.form_data_in import (
    AgentFormDataIn,
    CaseFormDataIn,
    ConnectionFormDataIn,
    OutputTypeFormDataIn,
    SamplingParamsFormDataIn,
    ToolFormDataIn,
    ToolGroupFormDataIn,
)
from chatddx.repo.form_data_out import (
    AgentFormDataOut,
    CaseFormDataOut,
    ConnectionFormDataOut,
    OutputTypeFormDataOut,
    SamplingParamsFormDataOut,
    ToolFormDataOut,
    ToolGroupFormDataOut,
)
from chatddx.repo.trail_models import (
    AgentTrailModel,
    CaseTrailModel,
    ConnectionTrailModel,
    OutputTypeTrailModel,
    SamplingParamsTrailModel,
    ToolGroupTrailModel,
    ToolTrailModel,
)
from chatddx.repo.trail_schema_refs import (
    AgentSchemaRef,
    CaseSchemaRef,
    ConnectionSchemaRef,
    OutputTypeSchemaRef,
    SamplingParamsSchemaRef,
    ToolGroupSchemaRef,
    ToolSchemaRef,
)
from chatddx.repo.trail_schemas import (
    AgentSchema,
    CaseSchema,
    ConnectionSchema,
    OutputTypeSchema,
    SamplingParamsSchema,
    ToolGroupSchema,
    ToolSchema,
)
from chatddx.repo.trail_specs import (
    AgentSpec,
    CaseSpec,
    ConnectionSpec,
    OutputTypeSpec,
    SamplingParamsSpec,
    ToolGroupSpec,
    ToolSpec,
)


@dataclass
class RepoBundle[
    TrailSchemaT: TrailSchema,
    TrailSpecT: TrailSpec,
]:
    TrailSchema: type[TrailSchemaT]
    TrailSchemaRef: type[TrailSchemaRef]
    TrailModel: type[TrailModel]
    TrailSpec: type[TrailSpecT]

    BranchSchema: type[BranchSchema[TrailSchemaT]]
    BranchModel: type[BranchModel]
    BranchSpec: type[BranchSpec[TrailSpecT]]

    BaseFormDataIn: type[BaseFormDataIn]
    BaseFormDataOut: type[BaseFormDataOut]
    BranchProxy: type[BranchProxy]


agent_bundle = RepoBundle(
    AgentSchema,
    AgentSchemaRef,
    AgentTrailModel,
    AgentSpec,
    BranchSchema[AgentSchema],
    AgentBranchModel,
    AgentBranchSpec,
    AgentFormDataIn,
    AgentFormDataOut,
    proxies.Agent,
)

connection_bundle = RepoBundle(
    ConnectionSchema,
    ConnectionSchemaRef,
    ConnectionTrailModel,
    ConnectionSpec,
    BranchSchema[ConnectionSchema],
    ConnectionBranchModel,
    ConnectionBranchSpec,
    ConnectionFormDataIn,
    ConnectionFormDataOut,
    proxies.Connection,
)

sampling_params_bundle = RepoBundle(
    SamplingParamsSchema,
    SamplingParamsSchemaRef,
    SamplingParamsTrailModel,
    SamplingParamsSpec,
    BranchSchema[SamplingParamsSchema],
    SamplingParamsBranchModel,
    SamplingParamsBranchSpec,
    SamplingParamsFormDataIn,
    SamplingParamsFormDataOut,
    proxies.SamplingParams,
)

output_type_bundle = RepoBundle(
    OutputTypeSchema,
    OutputTypeSchemaRef,
    OutputTypeTrailModel,
    OutputTypeSpec,
    BranchSchema[OutputTypeSchema],
    OutputTypeBranchModel,
    OutputTypeBranchSpec,
    OutputTypeFormDataIn,
    OutputTypeFormDataOut,
    proxies.OutputType,
)

tool_group_bundle = RepoBundle(
    ToolGroupSchema,
    ToolGroupSchemaRef,
    ToolGroupTrailModel,
    ToolGroupSpec,
    BranchSchema[ToolGroupSchema],
    ToolGroupBranchModel,
    ToolGroupBranchSpec,
    ToolGroupFormDataIn,
    ToolGroupFormDataOut,
    proxies.ToolGroup,
)

tool_bundle = RepoBundle(
    ToolSchema,
    ToolSchemaRef,
    ToolTrailModel,
    ToolSpec,
    BranchSchema[ToolSchema],
    ToolBranchModel,
    ToolBranchSpec,
    ToolFormDataIn,
    ToolFormDataOut,
    proxies.Tool,
)

case_bundle = RepoBundle(
    CaseSchema,
    CaseSchemaRef,
    CaseTrailModel,
    CaseSpec,
    BranchSchema[CaseSchema],
    CaseBranchModel,
    CaseBranchSpec,
    CaseFormDataIn,
    CaseFormDataOut,
    proxies.Case,
)


class RepoBundles(TypedDict):
    agent: RepoBundle[AgentSchema, AgentSpec]
    connection: RepoBundle[ConnectionSchema, ConnectionSpec]
    sampling_params: RepoBundle[SamplingParamsSchema, SamplingParamsSpec]
    output_type: RepoBundle[OutputTypeSchema, OutputTypeSpec]
    tool_group: RepoBundle[ToolGroupSchema, ToolGroupSpec]
    tool: RepoBundle[ToolSchema, ToolSpec]
    case: RepoBundle[CaseSchema, CaseSpec]


repo = RepoBundles(
    agent=agent_bundle,
    connection=connection_bundle,
    sampling_params=sampling_params_bundle,
    output_type=output_type_bundle,
    tool_group=tool_group_bundle,
    tool=tool_bundle,
    case=case_bundle,
)

BundleName = Literal[
    "agent",
    "connection",
    "sampling_params",
    "output_type",
    "tool_group",
    "tool",
    "case",
]

agent_relations: list[BundleName] = [
    "connection",
    "sampling_params",
    "output_type",
    "tool_group",
]


def is_bundle_name(val: str) -> TypeGuard[BundleName]:
    return val in get_args(BundleName)


_TYPE_TO_BUNDLE_REGISTRY: dict[type, RepoBundle[Any, Any]] = {}

bundle_obj: RepoBundle[Any, Any]
for bundle_obj in repo.values():  # pyright: ignore[reportAssignmentType]
    for field_meta in fields(bundle_obj):
        cls_type = getattr(bundle_obj, field_meta.name)
        if isinstance(cls_type, type):
            _TYPE_TO_BUNDLE_REGISTRY[cls_type] = bundle_obj


def get_bundle(identifier: BundleName | type | object) -> RepoBundle[Any, Any]:
    match identifier:
        case str():
            if identifier in repo:
                return repo[identifier]  # pyright: ignore[reportUnknownVariableType]
            raise KeyError(f"Bundle string '{identifier}' not found.")
        case type():
            if identifier in _TYPE_TO_BUNDLE_REGISTRY:
                return _TYPE_TO_BUNDLE_REGISTRY[identifier]
            raise TypeError(
                f"Type '{identifier.__name__}' is not mapped to any RepoBundle."
            )
        case object():
            obj_type = type(identifier)
            if obj_type in _TYPE_TO_BUNDLE_REGISTRY:
                return _TYPE_TO_BUNDLE_REGISTRY[obj_type]

            raise TypeError(
                f"Instance of '{obj_type.__name__}' is not mapped to any RepoBundle."
            )


def Repo[T: type](bundle_or_type: BundleName | type | object, field: T) -> T:
    bundle_obj = get_bundle(bundle_or_type)

    attr_name = getattr(field, "__name__", None)

    if attr_name and hasattr(bundle_obj, attr_name):
        return getattr(bundle_obj, attr_name)

    raise KeyError(f"Type '{field}' is not registered on the requested bundle.")
