from dataclasses import dataclass
from typing import Any, Literal

from chatddx.repo.entities.agent import (
    Agent as AgentProxy,
    AgentBranchModel,
    AgentBranchSchema,
    AgentBranchSpec,
    AgentFormDataIn,
    AgentFormDataOut,
    AgentTrailModel,
    AgentTrailSchema,
    AgentTrailSchemaRef,
    AgentTrailSpec,
)
from chatddx.repo.entities.case import (
    Case as CaseProxy,
    CaseBranchModel,
    CaseBranchSchema,
    CaseBranchSpec,
    CaseFormDataIn,
    CaseFormDataOut,
    CaseTrailModel,
    CaseTrailSchema,
    CaseTrailSchemaRef,
    CaseTrailSpec,
)
from chatddx.repo.entities.connection import (
    Connection as ConnectionProxy,
    ConnectionBranchModel,
    ConnectionBranchSchema,
    ConnectionBranchSpec,
    ConnectionFormDataIn,
    ConnectionFormDataOut,
    ConnectionTrailModel,
    ConnectionTrailSchema,
    ConnectionTrailSchemaRef,
    ConnectionTrailSpec,
)
from chatddx.repo.entities.expect import (
    Expect as ExpectProxy,
    ExpectBranchModel,
    ExpectBranchSchema,
    ExpectBranchSpec,
    ExpectFormDataIn,
    ExpectFormDataOut,
    ExpectTrailModel,
    ExpectTrailSchema,
    ExpectTrailSchemaRef,
    ExpectTrailSpec,
)
from chatddx.repo.entities.output_type import (
    OutputType as OutputTypeProxy,
    OutputTypeBranchModel,
    OutputTypeBranchSchema,
    OutputTypeBranchSpec,
    OutputTypeFormDataIn,
    OutputTypeFormDataOut,
    OutputTypeTrailModel,
    OutputTypeTrailSchema,
    OutputTypeTrailSchemaRef,
    OutputTypeTrailSpec,
)
from chatddx.repo.entities.sampling_params import (
    SamplingParams as SamplingParamsProxy,
    SamplingParamsBranchModel,
    SamplingParamsBranchSchema,
    SamplingParamsBranchSpec,
    SamplingParamsFormDataIn,
    SamplingParamsFormDataOut,
    SamplingParamsTrailModel,
    SamplingParamsTrailSchema,
    SamplingParamsTrailSchemaRef,
    SamplingParamsTrailSpec,
)
from chatddx.repo.entities.scorer import (
    Scorer as ScorerProxy,
    ScorerBranchModel,
    ScorerBranchSchema,
    ScorerBranchSpec,
    ScorerFormDataIn,
    ScorerFormDataOut,
    ScorerTrailModel,
    ScorerTrailSchema,
    ScorerTrailSchemaRef,
    ScorerTrailSpec,
)
from chatddx.repo.entities.super_agent import (
    SuperAgent as SuperAgentProxy,
    SuperAgentFormDataIn,
    SuperAgentFormDataOut,
)
from chatddx.repo.entities.tool import (
    Tool as ToolProxy,
    ToolBranchModel,
    ToolBranchSchema,
    ToolBranchSpec,
    ToolFormDataIn,
    ToolFormDataOut,
    ToolTrailModel,
    ToolTrailSchema,
    ToolTrailSchemaRef,
    ToolTrailSpec,
)
from chatddx.repo.entities.tool_group import (
    ToolGroup as ToolGroupProxy,
    ToolGroupBranchModel,
    ToolGroupBranchSchema,
    ToolGroupBranchSpec,
    ToolGroupFormDataIn,
    ToolGroupFormDataOut,
    ToolGroupTrailModel,
    ToolGroupTrailSchema,
    ToolGroupTrailSchemaRef,
    ToolGroupTrailSpec,
)
from chatddx.repo.families import (
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

type EntityName = Literal[
    "agent",
    "connection",
    "sampling_params",
    "output_type",
    "tool",
    "tool_group",
    "case",
    "scorer",
    "expect",
    "super_agent",
]


@dataclass(frozen=True)
class Bundle[
    BS: BranchSchema[Any],
    BP: BranchSpec[Any],
    TS: TrailSchema,
    TP: TrailSpec,
    TR: TrailSchemaRef,
    FDI: BaseFormDataIn,
    FDO: BaseFormDataOut,
    TM: TrailModel,
    BM: BranchModel,
    P: BranchProxy,
]:
    name: EntityName
    branch_schema: type[BS]
    branch_spec: type[BP]
    trail_schema: type[TS]
    trail_spec: type[TP]
    trail_schema_ref: type[TR]
    form_data_in: type[FDI]
    form_data_out: type[FDO]
    trail_model: type[TM]
    branch_model: type[BM]
    proxy: type[P]

    def members(self) -> tuple[type, ...]:
        return (
            self.branch_schema,
            self.branch_spec,
            self.trail_schema,
            self.trail_spec,
            self.trail_schema_ref,
            self.form_data_in,
            self.form_data_out,
            self.trail_model,
            self.branch_model,
            self.proxy,
        )


type AnyBundle = Bundle[
    BranchSchema[Any],
    BranchSpec[Any],
    TrailSchema,
    TrailSpec,
    TrailSchemaRef,
    BaseFormDataIn,
    BaseFormDataOut,
    TrailModel,
    BranchModel,
    BranchProxy,
]

type AnyMember = (
    BranchSchema[TrailSchema]
    | BranchSpec[TrailSpec]
    | TrailSchema
    | TrailSpec
    | TrailSchemaRef
    | BaseFormDataIn
    | BaseFormDataOut
    | TrailModel
    | BranchModel
    | BranchProxy
)

type SuperAgentBundle = Bundle[
    AgentBranchSchema,
    AgentBranchSpec,
    AgentTrailSchema,
    AgentTrailSpec,
    AgentTrailSchemaRef,
    SuperAgentFormDataIn,
    SuperAgentFormDataOut,
    AgentTrailModel,
    AgentBranchModel,
    SuperAgentProxy,
]

type SuperAgentMember = (
    AgentBranchSchema
    | AgentBranchSpec
    | AgentTrailSchema
    | AgentTrailSpec
    | AgentTrailSchemaRef
    | SuperAgentFormDataIn
    | SuperAgentFormDataOut
    | AgentTrailModel
    | AgentBranchModel
    | SuperAgentProxy
)

SUPER_AGENT: SuperAgentBundle = Bundle(
    name="super_agent",
    branch_schema=AgentBranchSchema,
    branch_spec=AgentBranchSpec,
    trail_schema=AgentTrailSchema,
    trail_spec=AgentTrailSpec,
    trail_schema_ref=AgentTrailSchemaRef,
    form_data_in=SuperAgentFormDataIn,
    form_data_out=SuperAgentFormDataOut,
    trail_model=AgentTrailModel,
    branch_model=AgentBranchModel,
    proxy=SuperAgentProxy,
)

type AgentBundle = Bundle[
    AgentBranchSchema,
    AgentBranchSpec,
    AgentTrailSchema,
    AgentTrailSpec,
    AgentTrailSchemaRef,
    AgentFormDataIn,
    AgentFormDataOut,
    AgentTrailModel,
    AgentBranchModel,
    AgentProxy,
]
type AgentMember = (
    AgentBranchSchema
    | AgentBranchSpec
    | AgentTrailSchema
    | AgentTrailSpec
    | AgentTrailSchemaRef
    | AgentFormDataIn
    | AgentFormDataOut
    | AgentTrailModel
    | AgentBranchModel
    | AgentProxy
)

AGENT: AgentBundle = Bundle(
    name="agent",
    branch_schema=AgentBranchSchema,
    branch_spec=AgentBranchSpec,
    trail_schema=AgentTrailSchema,
    trail_spec=AgentTrailSpec,
    trail_schema_ref=AgentTrailSchemaRef,
    form_data_in=AgentFormDataIn,
    form_data_out=AgentFormDataOut,
    trail_model=AgentTrailModel,
    branch_model=AgentBranchModel,
    proxy=AgentProxy,
)


type ConnectionBundle = Bundle[
    ConnectionBranchSchema,
    ConnectionBranchSpec,
    ConnectionTrailSchema,
    ConnectionTrailSpec,
    ConnectionTrailSchemaRef,
    ConnectionFormDataIn,
    ConnectionFormDataOut,
    ConnectionTrailModel,
    ConnectionBranchModel,
    ConnectionProxy,
]
type ConnectionMember = (
    ConnectionBranchSchema
    | ConnectionBranchSpec
    | ConnectionTrailSchema
    | ConnectionTrailSpec
    | ConnectionTrailSchemaRef
    | ConnectionFormDataIn
    | ConnectionFormDataOut
    | ConnectionTrailModel
    | ConnectionBranchModel
    | ConnectionProxy
)

CONNECTION: ConnectionBundle = Bundle(
    name="connection",
    branch_schema=ConnectionBranchSchema,
    branch_spec=ConnectionBranchSpec,
    trail_schema=ConnectionTrailSchema,
    trail_spec=ConnectionTrailSpec,
    trail_schema_ref=ConnectionTrailSchemaRef,
    form_data_in=ConnectionFormDataIn,
    form_data_out=ConnectionFormDataOut,
    trail_model=ConnectionTrailModel,
    branch_model=ConnectionBranchModel,
    proxy=ConnectionProxy,
)


type SamplingParamsBundle = Bundle[
    SamplingParamsBranchSchema,
    SamplingParamsBranchSpec,
    SamplingParamsTrailSchema,
    SamplingParamsTrailSpec,
    SamplingParamsTrailSchemaRef,
    SamplingParamsFormDataIn,
    SamplingParamsFormDataOut,
    SamplingParamsTrailModel,
    SamplingParamsBranchModel,
    SamplingParamsProxy,
]
type SamplingParamsMember = (
    SamplingParamsBranchSchema
    | SamplingParamsBranchSpec
    | SamplingParamsTrailSchema
    | SamplingParamsTrailSpec
    | SamplingParamsTrailSchemaRef
    | SamplingParamsFormDataIn
    | SamplingParamsFormDataOut
    | SamplingParamsTrailModel
    | SamplingParamsBranchModel
    | SamplingParamsProxy
)

SAMPLING_PARAMS: SamplingParamsBundle = Bundle(
    name="sampling_params",
    branch_schema=SamplingParamsBranchSchema,
    branch_spec=SamplingParamsBranchSpec,
    trail_schema=SamplingParamsTrailSchema,
    trail_spec=SamplingParamsTrailSpec,
    trail_schema_ref=SamplingParamsTrailSchemaRef,
    form_data_in=SamplingParamsFormDataIn,
    form_data_out=SamplingParamsFormDataOut,
    trail_model=SamplingParamsTrailModel,
    branch_model=SamplingParamsBranchModel,
    proxy=SamplingParamsProxy,
)


type OutputTypeBundle = Bundle[
    OutputTypeBranchSchema,
    OutputTypeBranchSpec,
    OutputTypeTrailSchema,
    OutputTypeTrailSpec,
    OutputTypeTrailSchemaRef,
    OutputTypeFormDataIn,
    OutputTypeFormDataOut,
    OutputTypeTrailModel,
    OutputTypeBranchModel,
    OutputTypeProxy,
]
type OutputTypeMember = (
    OutputTypeBranchSchema
    | OutputTypeBranchSpec
    | OutputTypeTrailSchema
    | OutputTypeTrailSpec
    | OutputTypeTrailSchemaRef
    | OutputTypeFormDataIn
    | OutputTypeFormDataOut
    | OutputTypeTrailModel
    | OutputTypeBranchModel
    | OutputTypeProxy
)

OUTPUT_TYPE: OutputTypeBundle = Bundle(
    name="output_type",
    branch_schema=OutputTypeBranchSchema,
    branch_spec=OutputTypeBranchSpec,
    trail_schema=OutputTypeTrailSchema,
    trail_spec=OutputTypeTrailSpec,
    trail_schema_ref=OutputTypeTrailSchemaRef,
    form_data_in=OutputTypeFormDataIn,
    form_data_out=OutputTypeFormDataOut,
    trail_model=OutputTypeTrailModel,
    branch_model=OutputTypeBranchModel,
    proxy=OutputTypeProxy,
)


type ToolBundle = Bundle[
    ToolBranchSchema,
    ToolBranchSpec,
    ToolTrailSchema,
    ToolTrailSpec,
    ToolTrailSchemaRef,
    ToolFormDataIn,
    ToolFormDataOut,
    ToolTrailModel,
    ToolBranchModel,
    ToolProxy,
]
type ToolMember = (
    ToolBranchSchema
    | ToolBranchSpec
    | ToolTrailSchema
    | ToolTrailSpec
    | ToolTrailSchemaRef
    | ToolFormDataIn
    | ToolFormDataOut
    | ToolTrailModel
    | ToolBranchModel
    | ToolProxy
)

TOOL: ToolBundle = Bundle(
    name="tool",
    branch_schema=ToolBranchSchema,
    branch_spec=ToolBranchSpec,
    trail_schema=ToolTrailSchema,
    trail_spec=ToolTrailSpec,
    trail_schema_ref=ToolTrailSchemaRef,
    form_data_in=ToolFormDataIn,
    form_data_out=ToolFormDataOut,
    trail_model=ToolTrailModel,
    branch_model=ToolBranchModel,
    proxy=ToolProxy,
)

type ToolGroupBundle = Bundle[
    ToolGroupBranchSchema,
    ToolGroupBranchSpec,
    ToolGroupTrailSchema,
    ToolGroupTrailSpec,
    ToolGroupTrailSchemaRef,
    ToolGroupFormDataIn,
    ToolGroupFormDataOut,
    ToolGroupTrailModel,
    ToolGroupBranchModel,
    ToolGroupProxy,
]

type ToolGroupMember = (
    ToolGroupBranchSchema
    | ToolGroupBranchSpec
    | ToolGroupTrailSchema
    | ToolGroupTrailSpec
    | ToolGroupTrailSchemaRef
    | ToolGroupFormDataIn
    | ToolGroupFormDataOut
    | ToolGroupTrailModel
    | ToolGroupBranchModel
    | ToolGroupProxy
)

TOOL_GROUP: ToolGroupBundle = Bundle(
    name="tool_group",
    branch_schema=ToolGroupBranchSchema,
    branch_spec=ToolGroupBranchSpec,
    trail_schema=ToolGroupTrailSchema,
    trail_spec=ToolGroupTrailSpec,
    trail_schema_ref=ToolGroupTrailSchemaRef,
    form_data_in=ToolGroupFormDataIn,
    form_data_out=ToolGroupFormDataOut,
    trail_model=ToolGroupTrailModel,
    branch_model=ToolGroupBranchModel,
    proxy=ToolGroupProxy,
)


type CaseBundle = Bundle[
    CaseBranchSchema,
    CaseBranchSpec,
    CaseTrailSchema,
    CaseTrailSpec,
    CaseTrailSchemaRef,
    CaseFormDataIn,
    CaseFormDataOut,
    CaseTrailModel,
    CaseBranchModel,
    CaseProxy,
]
type CaseMember = (
    CaseBranchSchema
    | CaseBranchSpec
    | CaseTrailSchema
    | CaseTrailSpec
    | CaseTrailSchemaRef
    | CaseFormDataIn
    | CaseFormDataOut
    | CaseTrailModel
    | CaseBranchModel
    | CaseProxy
)

CASE: CaseBundle = Bundle(
    name="case",
    branch_schema=CaseBranchSchema,
    branch_spec=CaseBranchSpec,
    trail_schema=CaseTrailSchema,
    trail_spec=CaseTrailSpec,
    trail_schema_ref=CaseTrailSchemaRef,
    form_data_in=CaseFormDataIn,
    form_data_out=CaseFormDataOut,
    trail_model=CaseTrailModel,
    branch_model=CaseBranchModel,
    proxy=CaseProxy,
)


type ScorerBundle = Bundle[
    ScorerBranchSchema,
    ScorerBranchSpec,
    ScorerTrailSchema,
    ScorerTrailSpec,
    ScorerTrailSchemaRef,
    ScorerFormDataIn,
    ScorerFormDataOut,
    ScorerTrailModel,
    ScorerBranchModel,
    ScorerProxy,
]
type ScorerMember = (
    ScorerBranchSchema
    | ScorerBranchSpec
    | ScorerTrailSchema
    | ScorerTrailSpec
    | ScorerTrailSchemaRef
    | ScorerFormDataIn
    | ScorerFormDataOut
    | ScorerTrailModel
    | ScorerBranchModel
    | ScorerProxy
)

SCORER: ScorerBundle = Bundle(
    name="scorer",
    branch_schema=ScorerBranchSchema,
    branch_spec=ScorerBranchSpec,
    trail_schema=ScorerTrailSchema,
    trail_spec=ScorerTrailSpec,
    trail_schema_ref=ScorerTrailSchemaRef,
    form_data_in=ScorerFormDataIn,
    form_data_out=ScorerFormDataOut,
    trail_model=ScorerTrailModel,
    branch_model=ScorerBranchModel,
    proxy=ScorerProxy,
)


type ExpectBundle = Bundle[
    ExpectBranchSchema,
    ExpectBranchSpec,
    ExpectTrailSchema,
    ExpectTrailSpec,
    ExpectTrailSchemaRef,
    ExpectFormDataIn,
    ExpectFormDataOut,
    ExpectTrailModel,
    ExpectBranchModel,
    ExpectProxy,
]
type ExpectMember = (
    ExpectBranchSchema
    | ExpectBranchSpec
    | ExpectTrailSchema
    | ExpectTrailSpec
    | ExpectTrailSchemaRef
    | ExpectFormDataIn
    | ExpectFormDataOut
    | ExpectTrailModel
    | ExpectBranchModel
    | ExpectProxy
)

EXPECT: ExpectBundle = Bundle(
    name="expect",
    branch_schema=ExpectBranchSchema,
    branch_spec=ExpectBranchSpec,
    trail_schema=ExpectTrailSchema,
    trail_spec=ExpectTrailSpec,
    trail_schema_ref=ExpectTrailSchemaRef,
    form_data_in=ExpectFormDataIn,
    form_data_out=ExpectFormDataOut,
    trail_model=ExpectTrailModel,
    branch_model=ExpectBranchModel,
    proxy=ExpectProxy,
)
