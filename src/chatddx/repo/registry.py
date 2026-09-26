from dataclasses import dataclass
from typing import Any

from chatddx.repo.entities.case import (
    Case as CaseProxy,
    CaseBranchDetails,
    CaseBranchDetailsPatch,
    CaseBranchIn,
    CaseBranchModel,
    CaseBranchOut,
    CaseFormDataIn,
    CaseFormDataOut,
    CaseTrailIn,
    CaseTrailModel,
    CaseTrailOut,
    CaseTrailRef,
    SharedCase as SharedCaseProxy,
)
from chatddx.repo.entities.client import (
    Client as ClientProxy,
    ClientBranchDetails,
    ClientBranchDetailsPatch,
    ClientBranchIn,
    ClientBranchModel,
    ClientBranchOut,
    ClientFormDataIn,
    ClientFormDataOut,
    ClientTrailIn,
    ClientTrailModel,
    ClientTrailOut,
    ClientTrailRef,
)
from chatddx.repo.entities.coercion import (
    Coercion as CoercionProxy,
    CoercionBranchIn,
    CoercionBranchModel,
    CoercionBranchOut,
    CoercionFormDataIn,
    CoercionFormDataOut,
    CoercionTrailIn,
    CoercionTrailModel,
    CoercionTrailOut,
    CoercionTrailRef,
)
from chatddx.repo.entities.configuration import (
    Configuration as ConfigurationProxy,
    ConfigurationBranchIn,
    ConfigurationBranchModel,
    ConfigurationBranchOut,
    ConfigurationFormDataIn,
    ConfigurationFormDataOut,
    ConfigurationTrailIn,
    ConfigurationTrailModel,
    ConfigurationTrailOut,
    ConfigurationTrailRef,
    SharedConfiguration as SharedConfigurationProxy,
)
from chatddx.repo.entities.instruction import (
    Instruction as InstructionProxy,
    InstructionBranchIn,
    InstructionBranchModel,
    InstructionBranchOut,
    InstructionFormDataIn,
    InstructionFormDataOut,
    InstructionTrailIn,
    InstructionTrailModel,
    InstructionTrailOut,
    InstructionTrailRef,
)
from chatddx.repo.entities.llm import (
    LLM as LLMProxy,
    LLMBranchDetails,
    LLMBranchDetailsPatch,
    LLMBranchIn,
    LLMBranchModel,
    LLMBranchOut,
    LLMFormDataIn,
    LLMFormDataOut,
    LLMTrailIn,
    LLMTrailModel,
    LLMTrailOut,
    LLMTrailRef,
)
from chatddx.repo.entities.machine import (
    Machine as MachineProxy,
    MachineBranchDetails,
    MachineBranchDetailsPatch,
    MachineBranchIn,
    MachineBranchModel,
    MachineBranchOut,
    MachineFormDataIn,
    MachineFormDataOut,
    MachineTrailIn,
    MachineTrailModel,
    MachineTrailOut,
    MachineTrailRef,
)
from chatddx.repo.entities.os import (
    Os as OsProxy,
    OsBranchDetails,
    OsBranchDetailsPatch,
    OsBranchIn,
    OsBranchModel,
    OsBranchOut,
    OsFormDataIn,
    OsFormDataOut,
    OsTrailIn,
    OsTrailModel,
    OsTrailOut,
    OsTrailRef,
)
from chatddx.repo.entities.output import (
    Output as OutputProxy,
    OutputBranchIn,
    OutputBranchModel,
    OutputBranchOut,
    OutputFormDataIn,
    OutputFormDataOut,
    OutputTrailIn,
    OutputTrailModel,
    OutputTrailOut,
    OutputTrailRef,
)
from chatddx.repo.entities.reasoning import (
    Reasoning as ReasoningProxy,
    ReasoningBranchIn,
    ReasoningBranchModel,
    ReasoningBranchOut,
    ReasoningFormDataIn,
    ReasoningFormDataOut,
    ReasoningTrailIn,
    ReasoningTrailModel,
    ReasoningTrailOut,
    ReasoningTrailRef,
)
from chatddx.repo.entities.sampling import (
    Sampling as SamplingProxy,
    SamplingBranchIn,
    SamplingBranchModel,
    SamplingBranchOut,
    SamplingFormDataIn,
    SamplingFormDataOut,
    SamplingTrailIn,
    SamplingTrailModel,
    SamplingTrailOut,
    SamplingTrailRef,
)
from chatddx.repo.entities.scorer import (
    Scorer as ScorerProxy,
    ScorerBranchDetails,
    ScorerBranchDetailsPatch,
    ScorerBranchIn,
    ScorerBranchModel,
    ScorerBranchOut,
    ScorerFormDataIn,
    ScorerFormDataOut,
    ScorerTrailIn,
    ScorerTrailModel,
    ScorerTrailOut,
    ScorerTrailRef,
)
from chatddx.repo.entities.serving import (
    Serving as ServingProxy,
    ServingBranchDetails,
    ServingBranchDetailsPatch,
    ServingBranchIn,
    ServingBranchModel,
    ServingBranchOut,
    ServingFormDataIn,
    ServingFormDataOut,
    ServingTrailIn,
    ServingTrailModel,
    ServingTrailOut,
    ServingTrailRef,
)
from chatddx.repo.entities.stack import (
    Stack as StackProxy,
    StackBranchDetails,
    StackBranchDetailsPatch,
    StackBranchIn,
    StackBranchModel,
    StackBranchOut,
    StackFormDataIn,
    StackFormDataOut,
    StackTrailIn,
    StackTrailModel,
    StackTrailOut,
    StackTrailRef,
)
from chatddx.repo.entities.tool import (
    Tool as ToolProxy,
    ToolBranchDetails,
    ToolBranchDetailsPatch,
    ToolBranchIn,
    ToolBranchModel,
    ToolBranchOut,
    ToolFormDataIn,
    ToolFormDataOut,
    ToolTrailIn,
    ToolTrailModel,
    ToolTrailOut,
    ToolTrailRef,
)
from chatddx.repo.entities.toolset import (
    Toolset as ToolsetProxy,
    ToolsetBranchIn,
    ToolsetBranchModel,
    ToolsetBranchOut,
    ToolsetFormDataIn,
    ToolsetFormDataOut,
    ToolsetTrailIn,
    ToolsetTrailModel,
    ToolsetTrailOut,
    ToolsetTrailRef,
)
from chatddx.repo.entity_names import EntityName, PresentationName
from chatddx.repo.families import (
    BaseBranch,
    BaseFormDataIn,
    BaseFormDataOut,
    BranchDetails,
    BranchDetailsPatch,
    BranchModel,
    BranchOut,
    BranchProxy,
    TrailIn,
    TrailModel,
    TrailOut,
    TrailRef,
)


@dataclass(frozen=True)
class Entity[
    BS: BaseBranch[Any],
    BP: BranchOut[Any, Any],
    TS: TrailIn,
    TP: TrailOut,
    TR: TrailRef,
    BD: BranchDetails,
    BDP: BranchDetailsPatch,
    TM: TrailModel,
    BM: BranchModel,
]:
    name: EntityName
    branch_in: type[BS]
    branch_out: type[BP]
    trail_in: type[TS]
    trail_out: type[TP]
    trail_ref: type[TR]
    branch_details: type[BD]
    branch_details_patch: type[BDP]
    trail_model: type[TM]
    branch_model: type[BM]

    def members(self) -> tuple[type, ...]:
        return (
            self.branch_in,
            self.branch_out,
            self.trail_in,
            self.trail_out,
            self.trail_ref,
            self.trail_model,
            self.branch_model,
        )


type AnyEntity = Entity[
    BaseBranch[Any],
    BranchOut[Any, Any],
    TrailIn,
    TrailOut,
    TrailRef,
    BranchDetails,
    BranchDetailsPatch,
    TrailModel,
    BranchModel,
]

type AnyEntityMember = (
    BaseBranch[Any]
    | BranchOut[Any, Any]
    | TrailIn
    | TrailOut
    | TrailRef
    | TrailModel
    | BranchModel
)


type MachineEntity = Entity[
    MachineBranchIn,
    MachineBranchOut,
    MachineTrailIn,
    MachineTrailOut,
    MachineTrailRef,
    MachineBranchDetails,
    MachineBranchDetailsPatch,
    MachineTrailModel,
    MachineBranchModel,
]
type MachineMember = (
    MachineBranchIn
    | MachineBranchOut
    | MachineTrailIn
    | MachineTrailOut
    | MachineTrailRef
    | MachineTrailModel
    | MachineBranchModel
)


type OsEntity = Entity[
    OsBranchIn,
    OsBranchOut,
    OsTrailIn,
    OsTrailOut,
    OsTrailRef,
    OsBranchDetails,
    OsBranchDetailsPatch,
    OsTrailModel,
    OsBranchModel,
]
type OsMember = (
    OsBranchIn
    | OsBranchOut
    | OsTrailIn
    | OsTrailOut
    | OsTrailRef
    | OsTrailModel
    | OsBranchModel
)


type LLMEntity = Entity[
    LLMBranchIn,
    LLMBranchOut,
    LLMTrailIn,
    LLMTrailOut,
    LLMTrailRef,
    LLMBranchDetails,
    LLMBranchDetailsPatch,
    LLMTrailModel,
    LLMBranchModel,
]
type LLMMember = (
    LLMBranchIn
    | LLMBranchOut
    | LLMTrailIn
    | LLMTrailOut
    | LLMTrailRef
    | LLMTrailModel
    | LLMBranchModel
)


type ServingEntity = Entity[
    ServingBranchIn,
    ServingBranchOut,
    ServingTrailIn,
    ServingTrailOut,
    ServingTrailRef,
    ServingBranchDetails,
    ServingBranchDetailsPatch,
    ServingTrailModel,
    ServingBranchModel,
]
type ServingMember = (
    ServingBranchIn
    | ServingBranchOut
    | ServingTrailIn
    | ServingTrailOut
    | ServingTrailRef
    | ServingTrailModel
    | ServingBranchModel
)


type ClientEntity = Entity[
    ClientBranchIn,
    ClientBranchOut,
    ClientTrailIn,
    ClientTrailOut,
    ClientTrailRef,
    ClientBranchDetails,
    ClientBranchDetailsPatch,
    ClientTrailModel,
    ClientBranchModel,
]
type ClientMember = (
    ClientBranchIn
    | ClientBranchOut
    | ClientTrailIn
    | ClientTrailOut
    | ClientTrailRef
    | ClientTrailModel
    | ClientBranchModel
)


type StackEntity = Entity[
    StackBranchIn,
    StackBranchOut,
    StackTrailIn,
    StackTrailOut,
    StackTrailRef,
    StackBranchDetails,
    StackBranchDetailsPatch,
    StackTrailModel,
    StackBranchModel,
]
type StackMember = (
    StackBranchIn
    | StackBranchOut
    | StackTrailIn
    | StackTrailOut
    | StackTrailRef
    | StackTrailModel
    | StackBranchModel
)


type ToolEntity = Entity[
    ToolBranchIn,
    ToolBranchOut,
    ToolTrailIn,
    ToolTrailOut,
    ToolTrailRef,
    ToolBranchDetails,
    ToolBranchDetailsPatch,
    ToolTrailModel,
    ToolBranchModel,
]
type ToolMember = (
    ToolBranchIn
    | ToolBranchOut
    | ToolTrailIn
    | ToolTrailOut
    | ToolTrailRef
    | ToolTrailModel
    | ToolBranchModel
)


type ToolsetEntity = Entity[
    ToolsetBranchIn,
    ToolsetBranchOut,
    ToolsetTrailIn,
    ToolsetTrailOut,
    ToolsetTrailRef,
    BranchDetails,
    BranchDetailsPatch,
    ToolsetTrailModel,
    ToolsetBranchModel,
]
type ToolsetMember = (
    ToolsetBranchIn
    | ToolsetBranchOut
    | ToolsetTrailIn
    | ToolsetTrailOut
    | ToolsetTrailRef
    | ToolsetTrailModel
    | ToolsetBranchModel
)


type InstructionEntity = Entity[
    InstructionBranchIn,
    InstructionBranchOut,
    InstructionTrailIn,
    InstructionTrailOut,
    InstructionTrailRef,
    BranchDetails,
    BranchDetailsPatch,
    InstructionTrailModel,
    InstructionBranchModel,
]
type InstructionMember = (
    InstructionBranchIn
    | InstructionBranchOut
    | InstructionTrailIn
    | InstructionTrailOut
    | InstructionTrailRef
    | InstructionTrailModel
    | InstructionBranchModel
)


type OutputEntity = Entity[
    OutputBranchIn,
    OutputBranchOut,
    OutputTrailIn,
    OutputTrailOut,
    OutputTrailRef,
    BranchDetails,
    BranchDetailsPatch,
    OutputTrailModel,
    OutputBranchModel,
]
type OutputMember = (
    OutputBranchIn
    | OutputBranchOut
    | OutputTrailIn
    | OutputTrailOut
    | OutputTrailRef
    | OutputTrailModel
    | OutputBranchModel
)


type CoercionEntity = Entity[
    CoercionBranchIn,
    CoercionBranchOut,
    CoercionTrailIn,
    CoercionTrailOut,
    CoercionTrailRef,
    BranchDetails,
    BranchDetailsPatch,
    CoercionTrailModel,
    CoercionBranchModel,
]
type CoercionMember = (
    CoercionBranchIn
    | CoercionBranchOut
    | CoercionTrailIn
    | CoercionTrailOut
    | CoercionTrailRef
    | CoercionTrailModel
    | CoercionBranchModel
)


type ReasoningEntity = Entity[
    ReasoningBranchIn,
    ReasoningBranchOut,
    ReasoningTrailIn,
    ReasoningTrailOut,
    ReasoningTrailRef,
    BranchDetails,
    BranchDetailsPatch,
    ReasoningTrailModel,
    ReasoningBranchModel,
]
type ReasoningMember = (
    ReasoningBranchIn
    | ReasoningBranchOut
    | ReasoningTrailIn
    | ReasoningTrailOut
    | ReasoningTrailRef
    | ReasoningTrailModel
    | ReasoningBranchModel
)


type SamplingEntity = Entity[
    SamplingBranchIn,
    SamplingBranchOut,
    SamplingTrailIn,
    SamplingTrailOut,
    SamplingTrailRef,
    BranchDetails,
    BranchDetailsPatch,
    SamplingTrailModel,
    SamplingBranchModel,
]
type SamplingMember = (
    SamplingBranchIn
    | SamplingBranchOut
    | SamplingTrailIn
    | SamplingTrailOut
    | SamplingTrailRef
    | SamplingTrailModel
    | SamplingBranchModel
)


type ConfigurationEntity = Entity[
    ConfigurationBranchIn,
    ConfigurationBranchOut,
    ConfigurationTrailIn,
    ConfigurationTrailOut,
    ConfigurationTrailRef,
    BranchDetails,
    BranchDetailsPatch,
    ConfigurationTrailModel,
    ConfigurationBranchModel,
]
type ConfigurationMember = (
    ConfigurationBranchIn
    | ConfigurationBranchOut
    | ConfigurationTrailIn
    | ConfigurationTrailOut
    | ConfigurationTrailRef
    | ConfigurationTrailModel
    | ConfigurationBranchModel
)


type CaseEntity = Entity[
    CaseBranchIn,
    CaseBranchOut,
    CaseTrailIn,
    CaseTrailOut,
    CaseTrailRef,
    CaseBranchDetails,
    CaseBranchDetailsPatch,
    CaseTrailModel,
    CaseBranchModel,
]
type CaseMember = (
    CaseBranchIn
    | CaseBranchOut
    | CaseTrailIn
    | CaseTrailOut
    | CaseTrailRef
    | CaseTrailModel
    | CaseBranchModel
)


type ScorerEntity = Entity[
    ScorerBranchIn,
    ScorerBranchOut,
    ScorerTrailIn,
    ScorerTrailOut,
    ScorerTrailRef,
    ScorerBranchDetails,
    ScorerBranchDetailsPatch,
    ScorerTrailModel,
    ScorerBranchModel,
]
type ScorerMember = (
    ScorerBranchIn
    | ScorerBranchOut
    | ScorerTrailIn
    | ScorerTrailOut
    | ScorerTrailRef
    | ScorerTrailModel
    | ScorerBranchModel
)


@dataclass(frozen=True)
class Presentation[
    P: BranchProxy,
    FDI: BaseFormDataIn,
    FDO: BaseFormDataOut,
]:
    name: PresentationName
    entity: AnyEntity
    proxy: type[P]
    shared_proxy: type[BranchProxy] | None
    form_data_in: type[FDI]
    form_data_out: type[FDO]

    def proxies(self) -> tuple[type, ...]:
        if self.shared_proxy is None:
            return (self.proxy,)

        return (self.proxy, self.shared_proxy)


type AnyPresentation = Presentation[BranchProxy, BaseFormDataIn, BaseFormDataOut]


MACHINE: MachineEntity = Entity(
    name="machine",
    branch_in=MachineBranchIn,
    branch_out=MachineBranchOut,
    trail_in=MachineTrailIn,
    trail_out=MachineTrailOut,
    trail_ref=MachineTrailRef,
    branch_details=MachineBranchDetails,
    branch_details_patch=MachineBranchDetailsPatch,
    trail_model=MachineTrailModel,
    branch_model=MachineBranchModel,
)

OS: OsEntity = Entity(
    name="os",
    branch_in=OsBranchIn,
    branch_out=OsBranchOut,
    trail_in=OsTrailIn,
    trail_out=OsTrailOut,
    trail_ref=OsTrailRef,
    branch_details=OsBranchDetails,
    branch_details_patch=OsBranchDetailsPatch,
    trail_model=OsTrailModel,
    branch_model=OsBranchModel,
)

LLM: LLMEntity = Entity(
    name="llm",
    branch_in=LLMBranchIn,
    branch_out=LLMBranchOut,
    trail_in=LLMTrailIn,
    trail_out=LLMTrailOut,
    trail_ref=LLMTrailRef,
    branch_details=LLMBranchDetails,
    branch_details_patch=LLMBranchDetailsPatch,
    trail_model=LLMTrailModel,
    branch_model=LLMBranchModel,
)

SERVING: ServingEntity = Entity(
    name="serving",
    branch_in=ServingBranchIn,
    branch_out=ServingBranchOut,
    trail_in=ServingTrailIn,
    trail_out=ServingTrailOut,
    trail_ref=ServingTrailRef,
    branch_details=ServingBranchDetails,
    branch_details_patch=ServingBranchDetailsPatch,
    trail_model=ServingTrailModel,
    branch_model=ServingBranchModel,
)

CLIENT: ClientEntity = Entity(
    name="client",
    branch_in=ClientBranchIn,
    branch_out=ClientBranchOut,
    trail_in=ClientTrailIn,
    trail_out=ClientTrailOut,
    trail_ref=ClientTrailRef,
    branch_details=ClientBranchDetails,
    branch_details_patch=ClientBranchDetailsPatch,
    trail_model=ClientTrailModel,
    branch_model=ClientBranchModel,
)

STACK: StackEntity = Entity(
    name="stack",
    branch_in=StackBranchIn,
    branch_out=StackBranchOut,
    trail_in=StackTrailIn,
    trail_out=StackTrailOut,
    trail_ref=StackTrailRef,
    branch_details=StackBranchDetails,
    branch_details_patch=StackBranchDetailsPatch,
    trail_model=StackTrailModel,
    branch_model=StackBranchModel,
)

TOOL: ToolEntity = Entity(
    name="tool",
    branch_in=ToolBranchIn,
    branch_out=ToolBranchOut,
    trail_in=ToolTrailIn,
    trail_out=ToolTrailOut,
    trail_ref=ToolTrailRef,
    branch_details=ToolBranchDetails,
    branch_details_patch=ToolBranchDetailsPatch,
    trail_model=ToolTrailModel,
    branch_model=ToolBranchModel,
)

TOOLSET: ToolsetEntity = Entity(
    name="toolset",
    branch_in=ToolsetBranchIn,
    branch_out=ToolsetBranchOut,
    trail_in=ToolsetTrailIn,
    trail_out=ToolsetTrailOut,
    trail_ref=ToolsetTrailRef,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ToolsetTrailModel,
    branch_model=ToolsetBranchModel,
)

INSTRUCTION: InstructionEntity = Entity(
    name="instruction",
    branch_in=InstructionBranchIn,
    branch_out=InstructionBranchOut,
    trail_in=InstructionTrailIn,
    trail_out=InstructionTrailOut,
    trail_ref=InstructionTrailRef,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=InstructionTrailModel,
    branch_model=InstructionBranchModel,
)

OUTPUT: OutputEntity = Entity(
    name="output",
    branch_in=OutputBranchIn,
    branch_out=OutputBranchOut,
    trail_in=OutputTrailIn,
    trail_out=OutputTrailOut,
    trail_ref=OutputTrailRef,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=OutputTrailModel,
    branch_model=OutputBranchModel,
)

COERCION: CoercionEntity = Entity(
    name="coercion",
    branch_in=CoercionBranchIn,
    branch_out=CoercionBranchOut,
    trail_in=CoercionTrailIn,
    trail_out=CoercionTrailOut,
    trail_ref=CoercionTrailRef,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=CoercionTrailModel,
    branch_model=CoercionBranchModel,
)

REASONING: ReasoningEntity = Entity(
    name="reasoning",
    branch_in=ReasoningBranchIn,
    branch_out=ReasoningBranchOut,
    trail_in=ReasoningTrailIn,
    trail_out=ReasoningTrailOut,
    trail_ref=ReasoningTrailRef,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ReasoningTrailModel,
    branch_model=ReasoningBranchModel,
)

SAMPLING: SamplingEntity = Entity(
    name="sampling",
    branch_in=SamplingBranchIn,
    branch_out=SamplingBranchOut,
    trail_in=SamplingTrailIn,
    trail_out=SamplingTrailOut,
    trail_ref=SamplingTrailRef,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=SamplingTrailModel,
    branch_model=SamplingBranchModel,
)

CONFIGURATION: ConfigurationEntity = Entity(
    name="configuration",
    branch_in=ConfigurationBranchIn,
    branch_out=ConfigurationBranchOut,
    trail_in=ConfigurationTrailIn,
    trail_out=ConfigurationTrailOut,
    trail_ref=ConfigurationTrailRef,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ConfigurationTrailModel,
    branch_model=ConfigurationBranchModel,
)

CASE: CaseEntity = Entity(
    name="case",
    branch_in=CaseBranchIn,
    branch_out=CaseBranchOut,
    trail_in=CaseTrailIn,
    trail_out=CaseTrailOut,
    trail_ref=CaseTrailRef,
    branch_details=CaseBranchDetails,
    branch_details_patch=CaseBranchDetailsPatch,
    trail_model=CaseTrailModel,
    branch_model=CaseBranchModel,
)

SCORER: ScorerEntity = Entity(
    name="scorer",
    branch_in=ScorerBranchIn,
    branch_out=ScorerBranchOut,
    trail_in=ScorerTrailIn,
    trail_out=ScorerTrailOut,
    trail_ref=ScorerTrailRef,
    branch_details=ScorerBranchDetails,
    branch_details_patch=ScorerBranchDetailsPatch,
    trail_model=ScorerTrailModel,
    branch_model=ScorerBranchModel,
)


MACHINE_PRESENTATION: Presentation[
    MachineProxy, MachineFormDataIn, MachineFormDataOut
] = Presentation(
    name="machine",
    entity=MACHINE,
    proxy=MachineProxy,
    shared_proxy=None,
    form_data_in=MachineFormDataIn,
    form_data_out=MachineFormDataOut,
)

OS_PRESENTATION: Presentation[OsProxy, OsFormDataIn, OsFormDataOut] = Presentation(
    name="os",
    entity=OS,
    proxy=OsProxy,
    shared_proxy=None,
    form_data_in=OsFormDataIn,
    form_data_out=OsFormDataOut,
)

LLM_PRESENTATION: Presentation[LLMProxy, LLMFormDataIn, LLMFormDataOut] = Presentation(
    name="llm",
    entity=LLM,
    proxy=LLMProxy,
    shared_proxy=None,
    form_data_in=LLMFormDataIn,
    form_data_out=LLMFormDataOut,
)

SERVING_PRESENTATION: Presentation[
    ServingProxy, ServingFormDataIn, ServingFormDataOut
] = Presentation(
    name="serving",
    entity=SERVING,
    proxy=ServingProxy,
    shared_proxy=None,
    form_data_in=ServingFormDataIn,
    form_data_out=ServingFormDataOut,
)

CLIENT_PRESENTATION: Presentation[ClientProxy, ClientFormDataIn, ClientFormDataOut] = (
    Presentation(
        name="client",
        entity=CLIENT,
        proxy=ClientProxy,
        shared_proxy=None,
        form_data_in=ClientFormDataIn,
        form_data_out=ClientFormDataOut,
    )
)

STACK_PRESENTATION: Presentation[StackProxy, StackFormDataIn, StackFormDataOut] = (
    Presentation(
        name="stack",
        entity=STACK,
        proxy=StackProxy,
        shared_proxy=None,
        form_data_in=StackFormDataIn,
        form_data_out=StackFormDataOut,
    )
)

TOOL_PRESENTATION: Presentation[ToolProxy, ToolFormDataIn, ToolFormDataOut] = (
    Presentation(
        name="tool",
        entity=TOOL,
        proxy=ToolProxy,
        shared_proxy=None,
        form_data_in=ToolFormDataIn,
        form_data_out=ToolFormDataOut,
    )
)

TOOLSET_PRESENTATION: Presentation[
    ToolsetProxy, ToolsetFormDataIn, ToolsetFormDataOut
] = Presentation(
    name="toolset",
    entity=TOOLSET,
    proxy=ToolsetProxy,
    shared_proxy=None,
    form_data_in=ToolsetFormDataIn,
    form_data_out=ToolsetFormDataOut,
)

INSTRUCTION_PRESENTATION: Presentation[
    InstructionProxy, InstructionFormDataIn, InstructionFormDataOut
] = Presentation(
    name="instruction",
    entity=INSTRUCTION,
    proxy=InstructionProxy,
    shared_proxy=None,
    form_data_in=InstructionFormDataIn,
    form_data_out=InstructionFormDataOut,
)

OUTPUT_PRESENTATION: Presentation[OutputProxy, OutputFormDataIn, OutputFormDataOut] = (
    Presentation(
        name="output",
        entity=OUTPUT,
        proxy=OutputProxy,
        shared_proxy=None,
        form_data_in=OutputFormDataIn,
        form_data_out=OutputFormDataOut,
    )
)

COERCION_PRESENTATION: Presentation[
    CoercionProxy, CoercionFormDataIn, CoercionFormDataOut
] = Presentation(
    name="coercion",
    entity=COERCION,
    proxy=CoercionProxy,
    shared_proxy=None,
    form_data_in=CoercionFormDataIn,
    form_data_out=CoercionFormDataOut,
)

REASONING_PRESENTATION: Presentation[
    ReasoningProxy, ReasoningFormDataIn, ReasoningFormDataOut
] = Presentation(
    name="reasoning",
    entity=REASONING,
    proxy=ReasoningProxy,
    shared_proxy=None,
    form_data_in=ReasoningFormDataIn,
    form_data_out=ReasoningFormDataOut,
)

SAMPLING_PRESENTATION: Presentation[
    SamplingProxy, SamplingFormDataIn, SamplingFormDataOut
] = Presentation(
    name="sampling",
    entity=SAMPLING,
    proxy=SamplingProxy,
    shared_proxy=None,
    form_data_in=SamplingFormDataIn,
    form_data_out=SamplingFormDataOut,
)

CONFIGURATION_PRESENTATION: Presentation[
    ConfigurationProxy, ConfigurationFormDataIn, ConfigurationFormDataOut
] = Presentation(
    name="configuration",
    entity=CONFIGURATION,
    proxy=ConfigurationProxy,
    shared_proxy=SharedConfigurationProxy,
    form_data_in=ConfigurationFormDataIn,
    form_data_out=ConfigurationFormDataOut,
)

CASE_PRESENTATION: Presentation[CaseProxy, CaseFormDataIn, CaseFormDataOut] = (
    Presentation(
        name="case",
        entity=CASE,
        proxy=CaseProxy,
        shared_proxy=SharedCaseProxy,
        form_data_in=CaseFormDataIn,
        form_data_out=CaseFormDataOut,
    )
)

SCORER_PRESENTATION: Presentation[ScorerProxy, ScorerFormDataIn, ScorerFormDataOut] = (
    Presentation(
        name="scorer",
        entity=SCORER,
        proxy=ScorerProxy,
        shared_proxy=None,
        form_data_in=ScorerFormDataIn,
        form_data_out=ScorerFormDataOut,
    )
)
