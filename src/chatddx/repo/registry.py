from dataclasses import dataclass
from typing import Any

from chatddx.repo.entities.case import (
    CaseBranchDetails,
    CaseBranchDetailsPatch,
    CaseBranchModel,
    CaseBranchOut,
    CaseTrailIn,
    CaseTrailModel,
    CaseTrailOut,
)
from chatddx.repo.entities.client import (
    ClientBranchDetails,
    ClientBranchDetailsPatch,
    ClientBranchModel,
    ClientBranchOut,
    ClientTrailIn,
    ClientTrailModel,
    ClientTrailOut,
)
from chatddx.repo.entities.coercion import (
    CoercionBranchModel,
    CoercionBranchOut,
    CoercionTrailIn,
    CoercionTrailModel,
    CoercionTrailOut,
)
from chatddx.repo.entities.configuration import (
    ConfigurationBranchModel,
    ConfigurationBranchOut,
    ConfigurationTrailIn,
    ConfigurationTrailModel,
    ConfigurationTrailOut,
)
from chatddx.repo.entities.instruction import (
    InstructionBranchModel,
    InstructionBranchOut,
    InstructionTrailIn,
    InstructionTrailModel,
    InstructionTrailOut,
)
from chatddx.repo.entities.llm import (
    LLMBranchDetails,
    LLMBranchDetailsPatch,
    LLMBranchModel,
    LLMBranchOut,
    LLMTrailIn,
    LLMTrailModel,
    LLMTrailOut,
)
from chatddx.repo.entities.machine import (
    MachineBranchDetails,
    MachineBranchDetailsPatch,
    MachineBranchModel,
    MachineBranchOut,
    MachineTrailIn,
    MachineTrailModel,
    MachineTrailOut,
)
from chatddx.repo.entities.os import (
    OsBranchDetails,
    OsBranchDetailsPatch,
    OsBranchModel,
    OsBranchOut,
    OsTrailIn,
    OsTrailModel,
    OsTrailOut,
)
from chatddx.repo.entities.output import (
    OutputBranchModel,
    OutputBranchOut,
    OutputTrailIn,
    OutputTrailModel,
    OutputTrailOut,
)
from chatddx.repo.entities.reasoning import (
    ReasoningBranchModel,
    ReasoningBranchOut,
    ReasoningTrailIn,
    ReasoningTrailModel,
    ReasoningTrailOut,
)
from chatddx.repo.entities.sampling import (
    SamplingBranchModel,
    SamplingBranchOut,
    SamplingTrailIn,
    SamplingTrailModel,
    SamplingTrailOut,
)
from chatddx.repo.entities.scorer import (
    ScorerBranchDetails,
    ScorerBranchDetailsPatch,
    ScorerBranchModel,
    ScorerBranchOut,
    ScorerTrailIn,
    ScorerTrailModel,
    ScorerTrailOut,
)
from chatddx.repo.entities.serving import (
    ServingBranchDetails,
    ServingBranchDetailsPatch,
    ServingBranchModel,
    ServingBranchOut,
    ServingTrailIn,
    ServingTrailModel,
    ServingTrailOut,
)
from chatddx.repo.entities.stack import (
    StackBranchDetails,
    StackBranchDetailsPatch,
    StackBranchModel,
    StackBranchOut,
    StackTrailIn,
    StackTrailModel,
    StackTrailOut,
)
from chatddx.repo.entities.tool import (
    ToolBranchDetails,
    ToolBranchDetailsPatch,
    ToolBranchModel,
    ToolBranchOut,
    ToolTrailIn,
    ToolTrailModel,
    ToolTrailOut,
)
from chatddx.repo.entities.toolset import (
    ToolsetBranchModel,
    ToolsetBranchOut,
    ToolsetTrailIn,
    ToolsetTrailModel,
    ToolsetTrailOut,
)
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families import (
    BranchDetails,
    BranchDetailsPatch,
    BranchModel,
    BranchOut,
    TrailIn,
    TrailModel,
    TrailOut,
)


@dataclass(frozen=True)
class Entity[
    BP: BranchOut[Any, Any],
    TS: TrailIn,
    TP: TrailOut,
    BD: BranchDetails,
    BDP: BranchDetailsPatch,
    TM: TrailModel,
    BM: BranchModel,
]:
    name: EntityName
    branch_out: type[BP]
    trail_in: type[TS]
    trail_out: type[TP]
    branch_details: type[BD]
    branch_details_patch: type[BDP]
    trail_model: type[TM]
    branch_model: type[BM]

    def members(self) -> tuple[type, ...]:
        return (
            self.branch_out,
            self.trail_in,
            self.trail_out,
            self.trail_model,
            self.branch_model,
        )


type AnyEntity = Entity[
    BranchOut[Any, Any],
    TrailIn,
    TrailOut,
    BranchDetails,
    BranchDetailsPatch,
    TrailModel,
    BranchModel,
]

type AnyEntityMember = (
    BranchOut[Any, Any] | TrailIn | TrailOut | TrailModel | BranchModel
)


type MachineEntity = Entity[
    MachineBranchOut,
    MachineTrailIn,
    MachineTrailOut,
    MachineBranchDetails,
    MachineBranchDetailsPatch,
    MachineTrailModel,
    MachineBranchModel,
]
type MachineMember = (
    MachineBranchOut
    | MachineTrailIn
    | MachineTrailOut
    | MachineTrailModel
    | MachineBranchModel
)


type OsEntity = Entity[
    OsBranchOut,
    OsTrailIn,
    OsTrailOut,
    OsBranchDetails,
    OsBranchDetailsPatch,
    OsTrailModel,
    OsBranchModel,
]
type OsMember = OsBranchOut | OsTrailIn | OsTrailOut | OsTrailModel | OsBranchModel


type LLMEntity = Entity[
    LLMBranchOut,
    LLMTrailIn,
    LLMTrailOut,
    LLMBranchDetails,
    LLMBranchDetailsPatch,
    LLMTrailModel,
    LLMBranchModel,
]
type LLMMember = (
    LLMBranchOut | LLMTrailIn | LLMTrailOut | LLMTrailModel | LLMBranchModel
)


type ServingEntity = Entity[
    ServingBranchOut,
    ServingTrailIn,
    ServingTrailOut,
    ServingBranchDetails,
    ServingBranchDetailsPatch,
    ServingTrailModel,
    ServingBranchModel,
]
type ServingMember = (
    ServingBranchOut
    | ServingTrailIn
    | ServingTrailOut
    | ServingTrailModel
    | ServingBranchModel
)


type ClientEntity = Entity[
    ClientBranchOut,
    ClientTrailIn,
    ClientTrailOut,
    ClientBranchDetails,
    ClientBranchDetailsPatch,
    ClientTrailModel,
    ClientBranchModel,
]
type ClientMember = (
    ClientBranchOut
    | ClientTrailIn
    | ClientTrailOut
    | ClientTrailModel
    | ClientBranchModel
)


type StackEntity = Entity[
    StackBranchOut,
    StackTrailIn,
    StackTrailOut,
    StackBranchDetails,
    StackBranchDetailsPatch,
    StackTrailModel,
    StackBranchModel,
]
type StackMember = (
    StackBranchOut | StackTrailIn | StackTrailOut | StackTrailModel | StackBranchModel
)


type ToolEntity = Entity[
    ToolBranchOut,
    ToolTrailIn,
    ToolTrailOut,
    ToolBranchDetails,
    ToolBranchDetailsPatch,
    ToolTrailModel,
    ToolBranchModel,
]
type ToolMember = (
    ToolBranchOut | ToolTrailIn | ToolTrailOut | ToolTrailModel | ToolBranchModel
)


type ToolsetEntity = Entity[
    ToolsetBranchOut,
    ToolsetTrailIn,
    ToolsetTrailOut,
    BranchDetails,
    BranchDetailsPatch,
    ToolsetTrailModel,
    ToolsetBranchModel,
]
type ToolsetMember = (
    ToolsetBranchOut
    | ToolsetTrailIn
    | ToolsetTrailOut
    | ToolsetTrailModel
    | ToolsetBranchModel
)


type InstructionEntity = Entity[
    InstructionBranchOut,
    InstructionTrailIn,
    InstructionTrailOut,
    BranchDetails,
    BranchDetailsPatch,
    InstructionTrailModel,
    InstructionBranchModel,
]
type InstructionMember = (
    InstructionBranchOut
    | InstructionTrailIn
    | InstructionTrailOut
    | InstructionTrailModel
    | InstructionBranchModel
)


type OutputEntity = Entity[
    OutputBranchOut,
    OutputTrailIn,
    OutputTrailOut,
    BranchDetails,
    BranchDetailsPatch,
    OutputTrailModel,
    OutputBranchModel,
]
type OutputMember = (
    OutputBranchOut
    | OutputTrailIn
    | OutputTrailOut
    | OutputTrailModel
    | OutputBranchModel
)


type CoercionEntity = Entity[
    CoercionBranchOut,
    CoercionTrailIn,
    CoercionTrailOut,
    BranchDetails,
    BranchDetailsPatch,
    CoercionTrailModel,
    CoercionBranchModel,
]
type CoercionMember = (
    CoercionBranchOut
    | CoercionTrailIn
    | CoercionTrailOut
    | CoercionTrailModel
    | CoercionBranchModel
)


type ReasoningEntity = Entity[
    ReasoningBranchOut,
    ReasoningTrailIn,
    ReasoningTrailOut,
    BranchDetails,
    BranchDetailsPatch,
    ReasoningTrailModel,
    ReasoningBranchModel,
]
type ReasoningMember = (
    ReasoningBranchOut
    | ReasoningTrailIn
    | ReasoningTrailOut
    | ReasoningTrailModel
    | ReasoningBranchModel
)


type SamplingEntity = Entity[
    SamplingBranchOut,
    SamplingTrailIn,
    SamplingTrailOut,
    BranchDetails,
    BranchDetailsPatch,
    SamplingTrailModel,
    SamplingBranchModel,
]
type SamplingMember = (
    SamplingBranchOut
    | SamplingTrailIn
    | SamplingTrailOut
    | SamplingTrailModel
    | SamplingBranchModel
)


type ConfigurationEntity = Entity[
    ConfigurationBranchOut,
    ConfigurationTrailIn,
    ConfigurationTrailOut,
    BranchDetails,
    BranchDetailsPatch,
    ConfigurationTrailModel,
    ConfigurationBranchModel,
]
type ConfigurationMember = (
    ConfigurationBranchOut
    | ConfigurationTrailIn
    | ConfigurationTrailOut
    | ConfigurationTrailModel
    | ConfigurationBranchModel
)


type CaseEntity = Entity[
    CaseBranchOut,
    CaseTrailIn,
    CaseTrailOut,
    CaseBranchDetails,
    CaseBranchDetailsPatch,
    CaseTrailModel,
    CaseBranchModel,
]
type CaseMember = (
    CaseBranchOut | CaseTrailIn | CaseTrailOut | CaseTrailModel | CaseBranchModel
)


type ScorerEntity = Entity[
    ScorerBranchOut,
    ScorerTrailIn,
    ScorerTrailOut,
    ScorerBranchDetails,
    ScorerBranchDetailsPatch,
    ScorerTrailModel,
    ScorerBranchModel,
]
type ScorerMember = (
    ScorerBranchOut
    | ScorerTrailIn
    | ScorerTrailOut
    | ScorerTrailModel
    | ScorerBranchModel
)


MACHINE: MachineEntity = Entity(
    name="machine",
    branch_out=MachineBranchOut,
    trail_in=MachineTrailIn,
    trail_out=MachineTrailOut,
    branch_details=MachineBranchDetails,
    branch_details_patch=MachineBranchDetailsPatch,
    trail_model=MachineTrailModel,
    branch_model=MachineBranchModel,
)

OS: OsEntity = Entity(
    name="os",
    branch_out=OsBranchOut,
    trail_in=OsTrailIn,
    trail_out=OsTrailOut,
    branch_details=OsBranchDetails,
    branch_details_patch=OsBranchDetailsPatch,
    trail_model=OsTrailModel,
    branch_model=OsBranchModel,
)

LLM: LLMEntity = Entity(
    name="llm",
    branch_out=LLMBranchOut,
    trail_in=LLMTrailIn,
    trail_out=LLMTrailOut,
    branch_details=LLMBranchDetails,
    branch_details_patch=LLMBranchDetailsPatch,
    trail_model=LLMTrailModel,
    branch_model=LLMBranchModel,
)

SERVING: ServingEntity = Entity(
    name="serving",
    branch_out=ServingBranchOut,
    trail_in=ServingTrailIn,
    trail_out=ServingTrailOut,
    branch_details=ServingBranchDetails,
    branch_details_patch=ServingBranchDetailsPatch,
    trail_model=ServingTrailModel,
    branch_model=ServingBranchModel,
)

CLIENT: ClientEntity = Entity(
    name="client",
    branch_out=ClientBranchOut,
    trail_in=ClientTrailIn,
    trail_out=ClientTrailOut,
    branch_details=ClientBranchDetails,
    branch_details_patch=ClientBranchDetailsPatch,
    trail_model=ClientTrailModel,
    branch_model=ClientBranchModel,
)

STACK: StackEntity = Entity(
    name="stack",
    branch_out=StackBranchOut,
    trail_in=StackTrailIn,
    trail_out=StackTrailOut,
    branch_details=StackBranchDetails,
    branch_details_patch=StackBranchDetailsPatch,
    trail_model=StackTrailModel,
    branch_model=StackBranchModel,
)

TOOL: ToolEntity = Entity(
    name="tool",
    branch_out=ToolBranchOut,
    trail_in=ToolTrailIn,
    trail_out=ToolTrailOut,
    branch_details=ToolBranchDetails,
    branch_details_patch=ToolBranchDetailsPatch,
    trail_model=ToolTrailModel,
    branch_model=ToolBranchModel,
)

TOOLSET: ToolsetEntity = Entity(
    name="toolset",
    branch_out=ToolsetBranchOut,
    trail_in=ToolsetTrailIn,
    trail_out=ToolsetTrailOut,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ToolsetTrailModel,
    branch_model=ToolsetBranchModel,
)

INSTRUCTION: InstructionEntity = Entity(
    name="instruction",
    branch_out=InstructionBranchOut,
    trail_in=InstructionTrailIn,
    trail_out=InstructionTrailOut,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=InstructionTrailModel,
    branch_model=InstructionBranchModel,
)

OUTPUT: OutputEntity = Entity(
    name="output",
    branch_out=OutputBranchOut,
    trail_in=OutputTrailIn,
    trail_out=OutputTrailOut,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=OutputTrailModel,
    branch_model=OutputBranchModel,
)

COERCION: CoercionEntity = Entity(
    name="coercion",
    branch_out=CoercionBranchOut,
    trail_in=CoercionTrailIn,
    trail_out=CoercionTrailOut,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=CoercionTrailModel,
    branch_model=CoercionBranchModel,
)

REASONING: ReasoningEntity = Entity(
    name="reasoning",
    branch_out=ReasoningBranchOut,
    trail_in=ReasoningTrailIn,
    trail_out=ReasoningTrailOut,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ReasoningTrailModel,
    branch_model=ReasoningBranchModel,
)

SAMPLING: SamplingEntity = Entity(
    name="sampling",
    branch_out=SamplingBranchOut,
    trail_in=SamplingTrailIn,
    trail_out=SamplingTrailOut,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=SamplingTrailModel,
    branch_model=SamplingBranchModel,
)

CONFIGURATION: ConfigurationEntity = Entity(
    name="configuration",
    branch_out=ConfigurationBranchOut,
    trail_in=ConfigurationTrailIn,
    trail_out=ConfigurationTrailOut,
    branch_details=BranchDetails,
    branch_details_patch=BranchDetailsPatch,
    trail_model=ConfigurationTrailModel,
    branch_model=ConfigurationBranchModel,
)

CASE: CaseEntity = Entity(
    name="case",
    branch_out=CaseBranchOut,
    trail_in=CaseTrailIn,
    trail_out=CaseTrailOut,
    branch_details=CaseBranchDetails,
    branch_details_patch=CaseBranchDetailsPatch,
    trail_model=CaseTrailModel,
    branch_model=CaseBranchModel,
)

SCORER: ScorerEntity = Entity(
    name="scorer",
    branch_out=ScorerBranchOut,
    trail_in=ScorerTrailIn,
    trail_out=ScorerTrailOut,
    branch_details=ScorerBranchDetails,
    branch_details_patch=ScorerBranchDetailsPatch,
    trail_model=ScorerTrailModel,
    branch_model=ScorerBranchModel,
)
