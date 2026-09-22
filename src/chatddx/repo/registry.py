from dataclasses import dataclass
from typing import Any

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
    SharedAgent as SharedAgentProxy,
)
from chatddx.repo.entities.case import (
    Case as CaseProxy,
    CaseBranchDetails,
    CaseBranchDetailsPatch,
    CaseBranchModel,
    CaseBranchSchema,
    CaseBranchSpec,
    CaseFormDataIn,
    CaseFormDataOut,
    CaseTrailModel,
    CaseTrailSchema,
    CaseTrailSchemaRef,
    CaseTrailSpec,
    SharedCase as SharedCaseProxy,
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
from chatddx.repo.entities.instruction import (
    Instruction as InstructionProxy,
    InstructionBranchModel,
    InstructionBranchSchema,
    InstructionBranchSpec,
    InstructionFormDataIn,
    InstructionFormDataOut,
    InstructionTrailModel,
    InstructionTrailSchema,
    InstructionTrailSchemaRef,
    InstructionTrailSpec,
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
    SharedScorer as SharedScorerProxy,
)
from chatddx.repo.entities.super_agent import (
    SharedSuperAgent as SharedSuperAgentProxy,
    SuperAgent as SuperAgentProxy,
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
from chatddx.repo.entity_names import EntityName, ViewName
from chatddx.repo.families import (
    BaseBranch,
    BaseFormDataIn,
    BaseFormDataOut,
    BranchDetailsPatch,
    BranchModel,
    BranchProxy,
    BranchSchemaDetails,
    BranchSpec,
    TrailModel,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)


@dataclass(frozen=True)
class Entity[
    BS: BaseBranch[Any],
    BP: BranchSpec[Any],
    TS: TrailSchema,
    TP: TrailSpec,
    TR: TrailSchemaRef,
    BD: BranchSchemaDetails,
    BDP: BranchDetailsPatch,
    TM: TrailModel,
    BM: BranchModel,
]:
    name: EntityName
    branch_schema: type[BS]
    branch_spec: type[BP]
    trail_schema: type[TS]
    trail_spec: type[TP]
    trail_schema_ref: type[TR]
    branch_details: type[BD]
    branch_details_patch: type[BDP]
    trail_model: type[TM]
    branch_model: type[BM]

    def members(self) -> tuple[type, ...]:
        return (
            self.branch_schema,
            self.branch_spec,
            self.trail_schema,
            self.trail_spec,
            self.trail_schema_ref,
            self.trail_model,
            self.branch_model,
        )


type AnyEntity = Entity[
    BaseBranch[Any],
    BranchSpec[Any],
    TrailSchema,
    TrailSpec,
    TrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    TrailModel,
    BranchModel,
]

type AnyEntityMember = (
    BaseBranch[Any]
    | BranchSpec[Any]
    | TrailSchema
    | TrailSpec
    | TrailSchemaRef
    | TrailModel
    | BranchModel
)


type AgentEntity = Entity[
    AgentBranchSchema,
    AgentBranchSpec,
    AgentTrailSchema,
    AgentTrailSpec,
    AgentTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    AgentTrailModel,
    AgentBranchModel,
]
type AgentMember = (
    AgentBranchSchema
    | AgentBranchSpec
    | AgentTrailSchema
    | AgentTrailSpec
    | AgentTrailSchemaRef
    | AgentTrailModel
    | AgentBranchModel
)


type InstructionEntity = Entity[
    InstructionBranchSchema,
    InstructionBranchSpec,
    InstructionTrailSchema,
    InstructionTrailSpec,
    InstructionTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    InstructionTrailModel,
    InstructionBranchModel,
]
type InstructionMember = (
    InstructionBranchSchema
    | InstructionBranchSpec
    | InstructionTrailSchema
    | InstructionTrailSpec
    | InstructionTrailSchemaRef
    | InstructionTrailModel
    | InstructionBranchModel
)


type ConnectionEntity = Entity[
    ConnectionBranchSchema,
    ConnectionBranchSpec,
    ConnectionTrailSchema,
    ConnectionTrailSpec,
    ConnectionTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    ConnectionTrailModel,
    ConnectionBranchModel,
]
type ConnectionMember = (
    ConnectionBranchSchema
    | ConnectionBranchSpec
    | ConnectionTrailSchema
    | ConnectionTrailSpec
    | ConnectionTrailSchemaRef
    | ConnectionTrailModel
    | ConnectionBranchModel
)


type SamplingParamsEntity = Entity[
    SamplingParamsBranchSchema,
    SamplingParamsBranchSpec,
    SamplingParamsTrailSchema,
    SamplingParamsTrailSpec,
    SamplingParamsTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    SamplingParamsTrailModel,
    SamplingParamsBranchModel,
]
type SamplingParamsMember = (
    SamplingParamsBranchSchema
    | SamplingParamsBranchSpec
    | SamplingParamsTrailSchema
    | SamplingParamsTrailSpec
    | SamplingParamsTrailSchemaRef
    | SamplingParamsTrailModel
    | SamplingParamsBranchModel
)


type OutputTypeEntity = Entity[
    OutputTypeBranchSchema,
    OutputTypeBranchSpec,
    OutputTypeTrailSchema,
    OutputTypeTrailSpec,
    OutputTypeTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    OutputTypeTrailModel,
    OutputTypeBranchModel,
]
type OutputTypeMember = (
    OutputTypeBranchSchema
    | OutputTypeBranchSpec
    | OutputTypeTrailSchema
    | OutputTypeTrailSpec
    | OutputTypeTrailSchemaRef
    | OutputTypeTrailModel
    | OutputTypeBranchModel
)


type ToolEntity = Entity[
    ToolBranchSchema,
    ToolBranchSpec,
    ToolTrailSchema,
    ToolTrailSpec,
    ToolTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    ToolTrailModel,
    ToolBranchModel,
]
type ToolMember = (
    ToolBranchSchema
    | ToolBranchSpec
    | ToolTrailSchema
    | ToolTrailSpec
    | ToolTrailSchemaRef
    | ToolTrailModel
    | ToolBranchModel
)


type ToolGroupEntity = Entity[
    ToolGroupBranchSchema,
    ToolGroupBranchSpec,
    ToolGroupTrailSchema,
    ToolGroupTrailSpec,
    ToolGroupTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    ToolGroupTrailModel,
    ToolGroupBranchModel,
]
type ToolGroupMember = (
    ToolGroupBranchSchema
    | ToolGroupBranchSpec
    | ToolGroupTrailSchema
    | ToolGroupTrailSpec
    | ToolGroupTrailSchemaRef
    | ToolGroupTrailModel
    | ToolGroupBranchModel
)


type ScorerEntity = Entity[
    ScorerBranchSchema,
    ScorerBranchSpec,
    ScorerTrailSchema,
    ScorerTrailSpec,
    ScorerTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    ScorerTrailModel,
    ScorerBranchModel,
]
type ScorerMember = (
    ScorerBranchSchema
    | ScorerBranchSpec
    | ScorerTrailSchema
    | ScorerTrailSpec
    | ScorerTrailSchemaRef
    | ScorerTrailModel
    | ScorerBranchModel
)


type ExpectEntity = Entity[
    ExpectBranchSchema,
    ExpectBranchSpec,
    ExpectTrailSchema,
    ExpectTrailSpec,
    ExpectTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    ExpectTrailModel,
    ExpectBranchModel,
]
type ExpectMember = (
    ExpectBranchSchema
    | ExpectBranchSpec
    | ExpectTrailSchema
    | ExpectTrailSpec
    | ExpectTrailSchemaRef
    | ExpectTrailModel
    | ExpectBranchModel
)


type CaseEntity = Entity[
    CaseBranchSchema,
    CaseBranchSpec,
    CaseTrailSchema,
    CaseTrailSpec,
    CaseTrailSchemaRef,
    CaseBranchDetails,
    CaseBranchDetailsPatch,
    CaseTrailModel,
    CaseBranchModel,
]
type CaseMember = (
    CaseBranchSchema
    | CaseBranchSpec
    | CaseTrailSchema
    | CaseTrailSpec
    | CaseTrailSchemaRef
    | CaseTrailModel
    | CaseBranchModel
)


@dataclass(frozen=True)
class View[
    P: BranchProxy,
    FDI: BaseFormDataIn,
    FDO: BaseFormDataOut,
]:
    name: ViewName
    entity: AnyEntity
    proxy: type[P]
    shared_proxy: type[BranchProxy] | None
    form_data_in: type[FDI]
    form_data_out: type[FDO]

    def proxies(self) -> tuple[type, ...]:
        if self.shared_proxy is None:
            return (self.proxy,)

        return (self.proxy, self.shared_proxy)


type AnyView = View[BranchProxy, BaseFormDataIn, BaseFormDataOut]


AGENT: AgentEntity = Entity(
    name="agent",
    branch_schema=AgentBranchSchema,
    branch_spec=AgentBranchSpec,
    trail_schema=AgentTrailSchema,
    trail_spec=AgentTrailSpec,
    trail_schema_ref=AgentTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=AgentTrailModel,
    branch_model=AgentBranchModel,
)

INSTRUCTION: InstructionEntity = Entity(
    name="instruction",
    branch_schema=InstructionBranchSchema,
    branch_spec=InstructionBranchSpec,
    trail_schema=InstructionTrailSchema,
    trail_spec=InstructionTrailSpec,
    trail_schema_ref=InstructionTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=InstructionTrailModel,
    branch_model=InstructionBranchModel,
)

CONNECTION: ConnectionEntity = Entity(
    name="connection",
    branch_schema=ConnectionBranchSchema,
    branch_spec=ConnectionBranchSpec,
    trail_schema=ConnectionTrailSchema,
    trail_spec=ConnectionTrailSpec,
    trail_schema_ref=ConnectionTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ConnectionTrailModel,
    branch_model=ConnectionBranchModel,
)

SAMPLING_PARAMS: SamplingParamsEntity = Entity(
    name="sampling_params",
    branch_schema=SamplingParamsBranchSchema,
    branch_spec=SamplingParamsBranchSpec,
    trail_schema=SamplingParamsTrailSchema,
    trail_spec=SamplingParamsTrailSpec,
    trail_schema_ref=SamplingParamsTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=SamplingParamsTrailModel,
    branch_model=SamplingParamsBranchModel,
)

OUTPUT_TYPE: OutputTypeEntity = Entity(
    name="output_type",
    branch_schema=OutputTypeBranchSchema,
    branch_spec=OutputTypeBranchSpec,
    trail_schema=OutputTypeTrailSchema,
    trail_spec=OutputTypeTrailSpec,
    trail_schema_ref=OutputTypeTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=OutputTypeTrailModel,
    branch_model=OutputTypeBranchModel,
)

TOOL: ToolEntity = Entity(
    name="tool",
    branch_schema=ToolBranchSchema,
    branch_spec=ToolBranchSpec,
    trail_schema=ToolTrailSchema,
    trail_spec=ToolTrailSpec,
    trail_schema_ref=ToolTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ToolTrailModel,
    branch_model=ToolBranchModel,
)

TOOL_GROUP: ToolGroupEntity = Entity(
    name="tool_group",
    branch_schema=ToolGroupBranchSchema,
    branch_spec=ToolGroupBranchSpec,
    trail_schema=ToolGroupTrailSchema,
    trail_spec=ToolGroupTrailSpec,
    trail_schema_ref=ToolGroupTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ToolGroupTrailModel,
    branch_model=ToolGroupBranchModel,
)

SCORER: ScorerEntity = Entity(
    name="scorer",
    branch_schema=ScorerBranchSchema,
    branch_spec=ScorerBranchSpec,
    trail_schema=ScorerTrailSchema,
    trail_spec=ScorerTrailSpec,
    trail_schema_ref=ScorerTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ScorerTrailModel,
    branch_model=ScorerBranchModel,
)

EXPECT: ExpectEntity = Entity(
    name="expect",
    branch_schema=ExpectBranchSchema,
    branch_spec=ExpectBranchSpec,
    trail_schema=ExpectTrailSchema,
    trail_spec=ExpectTrailSpec,
    trail_schema_ref=ExpectTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ExpectTrailModel,
    branch_model=ExpectBranchModel,
)

CASE: CaseEntity = Entity(
    name="case",
    branch_schema=CaseBranchSchema,
    branch_spec=CaseBranchSpec,
    trail_schema=CaseTrailSchema,
    trail_spec=CaseTrailSpec,
    trail_schema_ref=CaseTrailSchemaRef,
    # the only entity that carries more than collaborators and tags
    branch_details=CaseBranchDetails,
    branch_details_patch=CaseBranchDetailsPatch,
    trail_model=CaseTrailModel,
    branch_model=CaseBranchModel,
)


AGENT_VIEW: View[AgentProxy, AgentFormDataIn, AgentFormDataOut] = View(
    name="agent",
    entity=AGENT,
    proxy=AgentProxy,
    shared_proxy=SharedAgentProxy,
    form_data_in=AgentFormDataIn,
    form_data_out=AgentFormDataOut,
)

SUPER_AGENT_VIEW: View[SuperAgentProxy, AgentFormDataIn, SuperAgentFormDataOut] = View(
    name="super_agent",
    entity=AGENT,
    proxy=SuperAgentProxy,
    shared_proxy=SharedSuperAgentProxy,
    form_data_in=AgentFormDataIn,
    form_data_out=SuperAgentFormDataOut,
)

INSTRUCTION_VIEW: View[
    InstructionProxy, InstructionFormDataIn, InstructionFormDataOut
] = View(
    name="instruction",
    entity=INSTRUCTION,
    proxy=InstructionProxy,
    shared_proxy=None,
    form_data_in=InstructionFormDataIn,
    form_data_out=InstructionFormDataOut,
)

CONNECTION_VIEW: View[ConnectionProxy, ConnectionFormDataIn, ConnectionFormDataOut] = (
    View(
        name="connection",
        entity=CONNECTION,
        proxy=ConnectionProxy,
        shared_proxy=None,
        form_data_in=ConnectionFormDataIn,
        form_data_out=ConnectionFormDataOut,
    )
)

SAMPLING_PARAMS_VIEW: View[
    SamplingParamsProxy, SamplingParamsFormDataIn, SamplingParamsFormDataOut
] = View(
    name="sampling_params",
    entity=SAMPLING_PARAMS,
    proxy=SamplingParamsProxy,
    shared_proxy=None,
    form_data_in=SamplingParamsFormDataIn,
    form_data_out=SamplingParamsFormDataOut,
)

OUTPUT_TYPE_VIEW: View[OutputTypeProxy, OutputTypeFormDataIn, OutputTypeFormDataOut] = (
    View(
        name="output_type",
        entity=OUTPUT_TYPE,
        proxy=OutputTypeProxy,
        shared_proxy=None,
        form_data_in=OutputTypeFormDataIn,
        form_data_out=OutputTypeFormDataOut,
    )
)

TOOL_VIEW: View[ToolProxy, ToolFormDataIn, ToolFormDataOut] = View(
    name="tool",
    entity=TOOL,
    proxy=ToolProxy,
    shared_proxy=None,
    form_data_in=ToolFormDataIn,
    form_data_out=ToolFormDataOut,
)

TOOL_GROUP_VIEW: View[ToolGroupProxy, ToolGroupFormDataIn, ToolGroupFormDataOut] = View(
    name="tool_group",
    entity=TOOL_GROUP,
    proxy=ToolGroupProxy,
    shared_proxy=None,
    form_data_in=ToolGroupFormDataIn,
    form_data_out=ToolGroupFormDataOut,
)

SCORER_VIEW: View[ScorerProxy, ScorerFormDataIn, ScorerFormDataOut] = View(
    name="scorer",
    entity=SCORER,
    proxy=ScorerProxy,
    shared_proxy=SharedScorerProxy,
    form_data_in=ScorerFormDataIn,
    form_data_out=ScorerFormDataOut,
)

EXPECT_VIEW: View[ExpectProxy, ExpectFormDataIn, ExpectFormDataOut] = View(
    name="expect",
    entity=EXPECT,
    proxy=ExpectProxy,
    shared_proxy=None,
    form_data_in=ExpectFormDataIn,
    form_data_out=ExpectFormDataOut,
)

CASE_VIEW: View[CaseProxy, CaseFormDataIn, CaseFormDataOut] = View(
    name="case",
    entity=CASE,
    proxy=CaseProxy,
    shared_proxy=SharedCaseProxy,
    form_data_in=CaseFormDataIn,
    form_data_out=CaseFormDataOut,
)
