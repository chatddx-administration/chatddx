from dataclasses import dataclass
from typing import Any

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
    SharedCase as SharedCaseProxy,
)
from chatddx.repo.entities.client import (
    Client as ClientProxy,
    ClientBranchDetails,
    ClientBranchDetailsPatch,
    ClientBranchModel,
    ClientBranchSchema,
    ClientBranchSpec,
    ClientFormDataIn,
    ClientFormDataOut,
    ClientTrailModel,
    ClientTrailSchema,
    ClientTrailSchemaRef,
    ClientTrailSpec,
)
from chatddx.repo.entities.coercion import (
    Coercion as CoercionProxy,
    CoercionBranchModel,
    CoercionBranchSchema,
    CoercionBranchSpec,
    CoercionFormDataIn,
    CoercionFormDataOut,
    CoercionTrailModel,
    CoercionTrailSchema,
    CoercionTrailSchemaRef,
    CoercionTrailSpec,
)
from chatddx.repo.entities.configuration import (
    Configuration as ConfigurationProxy,
    ConfigurationBranchModel,
    ConfigurationBranchSchema,
    ConfigurationBranchSpec,
    ConfigurationFormDataIn,
    ConfigurationFormDataOut,
    ConfigurationTrailModel,
    ConfigurationTrailSchema,
    ConfigurationTrailSchemaRef,
    ConfigurationTrailSpec,
    SharedConfiguration as SharedConfigurationProxy,
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
from chatddx.repo.entities.machine import (
    Machine as MachineProxy,
    MachineBranchDetails,
    MachineBranchDetailsPatch,
    MachineBranchModel,
    MachineBranchSchema,
    MachineBranchSpec,
    MachineFormDataIn,
    MachineFormDataOut,
    MachineTrailModel,
    MachineTrailSchema,
    MachineTrailSchemaRef,
    MachineTrailSpec,
)
from chatddx.repo.entities.model import (
    LanguageModel as LanguageModelProxy,
    ModelBranchDetails,
    ModelBranchDetailsPatch,
    ModelBranchModel,
    ModelBranchSchema,
    ModelBranchSpec,
    ModelFormDataIn,
    ModelFormDataOut,
    ModelTrailModel,
    ModelTrailSchema,
    ModelTrailSchemaRef,
    ModelTrailSpec,
)
from chatddx.repo.entities.os import (
    Os as OsProxy,
    OsBranchDetails,
    OsBranchDetailsPatch,
    OsBranchModel,
    OsBranchSchema,
    OsBranchSpec,
    OsFormDataIn,
    OsFormDataOut,
    OsTrailModel,
    OsTrailSchema,
    OsTrailSchemaRef,
    OsTrailSpec,
)
from chatddx.repo.entities.output import (
    Output as OutputProxy,
    OutputBranchModel,
    OutputBranchSchema,
    OutputBranchSpec,
    OutputFormDataIn,
    OutputFormDataOut,
    OutputTrailModel,
    OutputTrailSchema,
    OutputTrailSchemaRef,
    OutputTrailSpec,
)
from chatddx.repo.entities.reasoning import (
    Reasoning as ReasoningProxy,
    ReasoningBranchModel,
    ReasoningBranchSchema,
    ReasoningBranchSpec,
    ReasoningFormDataIn,
    ReasoningFormDataOut,
    ReasoningTrailModel,
    ReasoningTrailSchema,
    ReasoningTrailSchemaRef,
    ReasoningTrailSpec,
)
from chatddx.repo.entities.sampling import (
    Sampling as SamplingProxy,
    SamplingBranchModel,
    SamplingBranchSchema,
    SamplingBranchSpec,
    SamplingFormDataIn,
    SamplingFormDataOut,
    SamplingTrailModel,
    SamplingTrailSchema,
    SamplingTrailSchemaRef,
    SamplingTrailSpec,
)
from chatddx.repo.entities.serving import (
    Serving as ServingProxy,
    ServingBranchDetails,
    ServingBranchDetailsPatch,
    ServingBranchModel,
    ServingBranchSchema,
    ServingBranchSpec,
    ServingFormDataIn,
    ServingFormDataOut,
    ServingTrailModel,
    ServingTrailSchema,
    ServingTrailSchemaRef,
    ServingTrailSpec,
)
from chatddx.repo.entities.stack import (
    Stack as StackProxy,
    StackBranchDetails,
    StackBranchDetailsPatch,
    StackBranchModel,
    StackBranchSchema,
    StackBranchSpec,
    StackFormDataIn,
    StackFormDataOut,
    StackTrailModel,
    StackTrailSchema,
    StackTrailSchemaRef,
    StackTrailSpec,
)
from chatddx.repo.entities.tool import (
    Tool as ToolProxy,
    ToolBranchDetails,
    ToolBranchDetailsPatch,
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
from chatddx.repo.entities.toolset import (
    Toolset as ToolsetProxy,
    ToolsetBranchModel,
    ToolsetBranchSchema,
    ToolsetBranchSpec,
    ToolsetFormDataIn,
    ToolsetFormDataOut,
    ToolsetTrailModel,
    ToolsetTrailSchema,
    ToolsetTrailSchemaRef,
    ToolsetTrailSpec,
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
    BP: BranchSpec[Any, Any],
    TS: TrailSchema,
    TP: TrailSpec,
    TR: TrailSchemaRef,
    BD: BranchSchemaDetails,
    BDP: BranchDetailsPatch,
    TM: TrailModel,
    BM: BranchModel,
]:
    """
    A registered kind of record, and its bundle: the schemas and models
    attached to it. Its content is a trail, content-addressed and immutable;
    an owner's named version of it is a branch, which also holds its details,
    what the branch says about the content without being part of it.
    """

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
    BranchSpec[Any, Any],
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
    | BranchSpec[Any, Any]
    | TrailSchema
    | TrailSpec
    | TrailSchemaRef
    | TrailModel
    | BranchModel
)


type MachineEntity = Entity[
    MachineBranchSchema,
    MachineBranchSpec,
    MachineTrailSchema,
    MachineTrailSpec,
    MachineTrailSchemaRef,
    MachineBranchDetails,
    MachineBranchDetailsPatch,
    MachineTrailModel,
    MachineBranchModel,
]
type MachineMember = (
    MachineBranchSchema
    | MachineBranchSpec
    | MachineTrailSchema
    | MachineTrailSpec
    | MachineTrailSchemaRef
    | MachineTrailModel
    | MachineBranchModel
)


type OsEntity = Entity[
    OsBranchSchema,
    OsBranchSpec,
    OsTrailSchema,
    OsTrailSpec,
    OsTrailSchemaRef,
    OsBranchDetails,
    OsBranchDetailsPatch,
    OsTrailModel,
    OsBranchModel,
]
type OsMember = (
    OsBranchSchema
    | OsBranchSpec
    | OsTrailSchema
    | OsTrailSpec
    | OsTrailSchemaRef
    | OsTrailModel
    | OsBranchModel
)


type ModelEntity = Entity[
    ModelBranchSchema,
    ModelBranchSpec,
    ModelTrailSchema,
    ModelTrailSpec,
    ModelTrailSchemaRef,
    ModelBranchDetails,
    ModelBranchDetailsPatch,
    ModelTrailModel,
    ModelBranchModel,
]
type ModelMember = (
    ModelBranchSchema
    | ModelBranchSpec
    | ModelTrailSchema
    | ModelTrailSpec
    | ModelTrailSchemaRef
    | ModelTrailModel
    | ModelBranchModel
)


type ServingEntity = Entity[
    ServingBranchSchema,
    ServingBranchSpec,
    ServingTrailSchema,
    ServingTrailSpec,
    ServingTrailSchemaRef,
    ServingBranchDetails,
    ServingBranchDetailsPatch,
    ServingTrailModel,
    ServingBranchModel,
]
type ServingMember = (
    ServingBranchSchema
    | ServingBranchSpec
    | ServingTrailSchema
    | ServingTrailSpec
    | ServingTrailSchemaRef
    | ServingTrailModel
    | ServingBranchModel
)


type ClientEntity = Entity[
    ClientBranchSchema,
    ClientBranchSpec,
    ClientTrailSchema,
    ClientTrailSpec,
    ClientTrailSchemaRef,
    ClientBranchDetails,
    ClientBranchDetailsPatch,
    ClientTrailModel,
    ClientBranchModel,
]
type ClientMember = (
    ClientBranchSchema
    | ClientBranchSpec
    | ClientTrailSchema
    | ClientTrailSpec
    | ClientTrailSchemaRef
    | ClientTrailModel
    | ClientBranchModel
)


type StackEntity = Entity[
    StackBranchSchema,
    StackBranchSpec,
    StackTrailSchema,
    StackTrailSpec,
    StackTrailSchemaRef,
    StackBranchDetails,
    StackBranchDetailsPatch,
    StackTrailModel,
    StackBranchModel,
]
type StackMember = (
    StackBranchSchema
    | StackBranchSpec
    | StackTrailSchema
    | StackTrailSpec
    | StackTrailSchemaRef
    | StackTrailModel
    | StackBranchModel
)


type ToolEntity = Entity[
    ToolBranchSchema,
    ToolBranchSpec,
    ToolTrailSchema,
    ToolTrailSpec,
    ToolTrailSchemaRef,
    ToolBranchDetails,
    ToolBranchDetailsPatch,
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


type ToolsetEntity = Entity[
    ToolsetBranchSchema,
    ToolsetBranchSpec,
    ToolsetTrailSchema,
    ToolsetTrailSpec,
    ToolsetTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    ToolsetTrailModel,
    ToolsetBranchModel,
]
type ToolsetMember = (
    ToolsetBranchSchema
    | ToolsetBranchSpec
    | ToolsetTrailSchema
    | ToolsetTrailSpec
    | ToolsetTrailSchemaRef
    | ToolsetTrailModel
    | ToolsetBranchModel
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


type OutputEntity = Entity[
    OutputBranchSchema,
    OutputBranchSpec,
    OutputTrailSchema,
    OutputTrailSpec,
    OutputTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    OutputTrailModel,
    OutputBranchModel,
]
type OutputMember = (
    OutputBranchSchema
    | OutputBranchSpec
    | OutputTrailSchema
    | OutputTrailSpec
    | OutputTrailSchemaRef
    | OutputTrailModel
    | OutputBranchModel
)


type CoercionEntity = Entity[
    CoercionBranchSchema,
    CoercionBranchSpec,
    CoercionTrailSchema,
    CoercionTrailSpec,
    CoercionTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    CoercionTrailModel,
    CoercionBranchModel,
]
type CoercionMember = (
    CoercionBranchSchema
    | CoercionBranchSpec
    | CoercionTrailSchema
    | CoercionTrailSpec
    | CoercionTrailSchemaRef
    | CoercionTrailModel
    | CoercionBranchModel
)


type ReasoningEntity = Entity[
    ReasoningBranchSchema,
    ReasoningBranchSpec,
    ReasoningTrailSchema,
    ReasoningTrailSpec,
    ReasoningTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    ReasoningTrailModel,
    ReasoningBranchModel,
]
type ReasoningMember = (
    ReasoningBranchSchema
    | ReasoningBranchSpec
    | ReasoningTrailSchema
    | ReasoningTrailSpec
    | ReasoningTrailSchemaRef
    | ReasoningTrailModel
    | ReasoningBranchModel
)


type SamplingEntity = Entity[
    SamplingBranchSchema,
    SamplingBranchSpec,
    SamplingTrailSchema,
    SamplingTrailSpec,
    SamplingTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    SamplingTrailModel,
    SamplingBranchModel,
]
type SamplingMember = (
    SamplingBranchSchema
    | SamplingBranchSpec
    | SamplingTrailSchema
    | SamplingTrailSpec
    | SamplingTrailSchemaRef
    | SamplingTrailModel
    | SamplingBranchModel
)


type ConfigurationEntity = Entity[
    ConfigurationBranchSchema,
    ConfigurationBranchSpec,
    ConfigurationTrailSchema,
    ConfigurationTrailSpec,
    ConfigurationTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
    ConfigurationTrailModel,
    ConfigurationBranchModel,
]
type ConfigurationMember = (
    ConfigurationBranchSchema
    | ConfigurationBranchSpec
    | ConfigurationTrailSchema
    | ConfigurationTrailSpec
    | ConfigurationTrailSchemaRef
    | ConfigurationTrailModel
    | ConfigurationBranchModel
)


type CaseEntity = Entity[
    CaseBranchSchema,
    CaseBranchSpec,
    CaseTrailSchema,
    CaseTrailSpec,
    CaseTrailSchemaRef,
    BranchSchemaDetails,
    BranchDetailsPatch,
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
    """How an entity is presented: its proxies and its form data."""

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


MACHINE: MachineEntity = Entity(
    name="machine",
    branch_schema=MachineBranchSchema,
    branch_spec=MachineBranchSpec,
    trail_schema=MachineTrailSchema,
    trail_spec=MachineTrailSpec,
    trail_schema_ref=MachineTrailSchemaRef,
    branch_details=MachineBranchDetails,
    branch_details_patch=MachineBranchDetailsPatch,
    trail_model=MachineTrailModel,
    branch_model=MachineBranchModel,
)

OS: OsEntity = Entity(
    name="os",
    branch_schema=OsBranchSchema,
    branch_spec=OsBranchSpec,
    trail_schema=OsTrailSchema,
    trail_spec=OsTrailSpec,
    trail_schema_ref=OsTrailSchemaRef,
    branch_details=OsBranchDetails,
    branch_details_patch=OsBranchDetailsPatch,
    trail_model=OsTrailModel,
    branch_model=OsBranchModel,
)

MODEL: ModelEntity = Entity(
    name="model",
    branch_schema=ModelBranchSchema,
    branch_spec=ModelBranchSpec,
    trail_schema=ModelTrailSchema,
    trail_spec=ModelTrailSpec,
    trail_schema_ref=ModelTrailSchemaRef,
    branch_details=ModelBranchDetails,
    branch_details_patch=ModelBranchDetailsPatch,
    trail_model=ModelTrailModel,
    branch_model=ModelBranchModel,
)

SERVING: ServingEntity = Entity(
    name="serving",
    branch_schema=ServingBranchSchema,
    branch_spec=ServingBranchSpec,
    trail_schema=ServingTrailSchema,
    trail_spec=ServingTrailSpec,
    trail_schema_ref=ServingTrailSchemaRef,
    branch_details=ServingBranchDetails,
    branch_details_patch=ServingBranchDetailsPatch,
    trail_model=ServingTrailModel,
    branch_model=ServingBranchModel,
)

CLIENT: ClientEntity = Entity(
    name="client",
    branch_schema=ClientBranchSchema,
    branch_spec=ClientBranchSpec,
    trail_schema=ClientTrailSchema,
    trail_spec=ClientTrailSpec,
    trail_schema_ref=ClientTrailSchemaRef,
    branch_details=ClientBranchDetails,
    branch_details_patch=ClientBranchDetailsPatch,
    trail_model=ClientTrailModel,
    branch_model=ClientBranchModel,
)

STACK: StackEntity = Entity(
    name="stack",
    branch_schema=StackBranchSchema,
    branch_spec=StackBranchSpec,
    trail_schema=StackTrailSchema,
    trail_spec=StackTrailSpec,
    trail_schema_ref=StackTrailSchemaRef,
    branch_details=StackBranchDetails,
    branch_details_patch=StackBranchDetailsPatch,
    trail_model=StackTrailModel,
    branch_model=StackBranchModel,
)

TOOL: ToolEntity = Entity(
    name="tool",
    branch_schema=ToolBranchSchema,
    branch_spec=ToolBranchSpec,
    trail_schema=ToolTrailSchema,
    trail_spec=ToolTrailSpec,
    trail_schema_ref=ToolTrailSchemaRef,
    branch_details=ToolBranchDetails,
    branch_details_patch=ToolBranchDetailsPatch,
    trail_model=ToolTrailModel,
    branch_model=ToolBranchModel,
)

TOOLSET: ToolsetEntity = Entity(
    name="toolset",
    branch_schema=ToolsetBranchSchema,
    branch_spec=ToolsetBranchSpec,
    trail_schema=ToolsetTrailSchema,
    trail_spec=ToolsetTrailSpec,
    trail_schema_ref=ToolsetTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ToolsetTrailModel,
    branch_model=ToolsetBranchModel,
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

OUTPUT: OutputEntity = Entity(
    name="output",
    branch_schema=OutputBranchSchema,
    branch_spec=OutputBranchSpec,
    trail_schema=OutputTrailSchema,
    trail_spec=OutputTrailSpec,
    trail_schema_ref=OutputTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=OutputTrailModel,
    branch_model=OutputBranchModel,
)

COERCION: CoercionEntity = Entity(
    name="coercion",
    branch_schema=CoercionBranchSchema,
    branch_spec=CoercionBranchSpec,
    trail_schema=CoercionTrailSchema,
    trail_spec=CoercionTrailSpec,
    trail_schema_ref=CoercionTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=CoercionTrailModel,
    branch_model=CoercionBranchModel,
)

REASONING: ReasoningEntity = Entity(
    name="reasoning",
    branch_schema=ReasoningBranchSchema,
    branch_spec=ReasoningBranchSpec,
    trail_schema=ReasoningTrailSchema,
    trail_spec=ReasoningTrailSpec,
    trail_schema_ref=ReasoningTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ReasoningTrailModel,
    branch_model=ReasoningBranchModel,
)

SAMPLING: SamplingEntity = Entity(
    name="sampling",
    branch_schema=SamplingBranchSchema,
    branch_spec=SamplingBranchSpec,
    trail_schema=SamplingTrailSchema,
    trail_spec=SamplingTrailSpec,
    trail_schema_ref=SamplingTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=SamplingTrailModel,
    branch_model=SamplingBranchModel,
)

CONFIGURATION: ConfigurationEntity = Entity(
    name="configuration",
    branch_schema=ConfigurationBranchSchema,
    branch_spec=ConfigurationBranchSpec,
    trail_schema=ConfigurationTrailSchema,
    trail_spec=ConfigurationTrailSpec,
    trail_schema_ref=ConfigurationTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ConfigurationTrailModel,
    branch_model=ConfigurationBranchModel,
)

CASE: CaseEntity = Entity(
    name="case",
    branch_schema=CaseBranchSchema,
    branch_spec=CaseBranchSpec,
    trail_schema=CaseTrailSchema,
    trail_spec=CaseTrailSpec,
    trail_schema_ref=CaseTrailSchemaRef,
    branch_details=BranchSchemaDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=CaseTrailModel,
    branch_model=CaseBranchModel,
)


MACHINE_VIEW: View[MachineProxy, MachineFormDataIn, MachineFormDataOut] = View(
    name="machine",
    entity=MACHINE,
    proxy=MachineProxy,
    shared_proxy=None,
    form_data_in=MachineFormDataIn,
    form_data_out=MachineFormDataOut,
)

OS_VIEW: View[OsProxy, OsFormDataIn, OsFormDataOut] = View(
    name="os",
    entity=OS,
    proxy=OsProxy,
    shared_proxy=None,
    form_data_in=OsFormDataIn,
    form_data_out=OsFormDataOut,
)

MODEL_VIEW: View[LanguageModelProxy, ModelFormDataIn, ModelFormDataOut] = View(
    name="model",
    entity=MODEL,
    proxy=LanguageModelProxy,
    shared_proxy=None,
    form_data_in=ModelFormDataIn,
    form_data_out=ModelFormDataOut,
)

SERVING_VIEW: View[ServingProxy, ServingFormDataIn, ServingFormDataOut] = View(
    name="serving",
    entity=SERVING,
    proxy=ServingProxy,
    shared_proxy=None,
    form_data_in=ServingFormDataIn,
    form_data_out=ServingFormDataOut,
)

CLIENT_VIEW: View[ClientProxy, ClientFormDataIn, ClientFormDataOut] = View(
    name="client",
    entity=CLIENT,
    proxy=ClientProxy,
    shared_proxy=None,
    form_data_in=ClientFormDataIn,
    form_data_out=ClientFormDataOut,
)

STACK_VIEW: View[StackProxy, StackFormDataIn, StackFormDataOut] = View(
    name="stack",
    entity=STACK,
    proxy=StackProxy,
    shared_proxy=None,
    form_data_in=StackFormDataIn,
    form_data_out=StackFormDataOut,
)

TOOL_VIEW: View[ToolProxy, ToolFormDataIn, ToolFormDataOut] = View(
    name="tool",
    entity=TOOL,
    proxy=ToolProxy,
    shared_proxy=None,
    form_data_in=ToolFormDataIn,
    form_data_out=ToolFormDataOut,
)

TOOLSET_VIEW: View[ToolsetProxy, ToolsetFormDataIn, ToolsetFormDataOut] = View(
    name="toolset",
    entity=TOOLSET,
    proxy=ToolsetProxy,
    shared_proxy=None,
    form_data_in=ToolsetFormDataIn,
    form_data_out=ToolsetFormDataOut,
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

OUTPUT_VIEW: View[OutputProxy, OutputFormDataIn, OutputFormDataOut] = View(
    name="output",
    entity=OUTPUT,
    proxy=OutputProxy,
    shared_proxy=None,
    form_data_in=OutputFormDataIn,
    form_data_out=OutputFormDataOut,
)

COERCION_VIEW: View[CoercionProxy, CoercionFormDataIn, CoercionFormDataOut] = View(
    name="coercion",
    entity=COERCION,
    proxy=CoercionProxy,
    shared_proxy=None,
    form_data_in=CoercionFormDataIn,
    form_data_out=CoercionFormDataOut,
)

REASONING_VIEW: View[ReasoningProxy, ReasoningFormDataIn, ReasoningFormDataOut] = View(
    name="reasoning",
    entity=REASONING,
    proxy=ReasoningProxy,
    shared_proxy=None,
    form_data_in=ReasoningFormDataIn,
    form_data_out=ReasoningFormDataOut,
)

SAMPLING_VIEW: View[SamplingProxy, SamplingFormDataIn, SamplingFormDataOut] = View(
    name="sampling",
    entity=SAMPLING,
    proxy=SamplingProxy,
    shared_proxy=None,
    form_data_in=SamplingFormDataIn,
    form_data_out=SamplingFormDataOut,
)

CONFIGURATION_VIEW: View[
    ConfigurationProxy, ConfigurationFormDataIn, ConfigurationFormDataOut
] = View(
    name="configuration",
    entity=CONFIGURATION,
    proxy=ConfigurationProxy,
    shared_proxy=SharedConfigurationProxy,
    form_data_in=ConfigurationFormDataIn,
    form_data_out=ConfigurationFormDataOut,
)

CASE_VIEW: View[CaseProxy, CaseFormDataIn, CaseFormDataOut] = View(
    name="case",
    entity=CASE,
    proxy=CaseProxy,
    shared_proxy=SharedCaseProxy,
    form_data_in=CaseFormDataIn,
    form_data_out=CaseFormDataOut,
)
