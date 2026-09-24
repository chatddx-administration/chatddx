"""
An inventory: every entity's records by name, in one of the forms a record
takes on its way from an inventory file to the database and back.
"""

from typing import TypedDict

from pydantic import BaseModel

from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import (
    CaseBranchDetailsPatch,
    CaseBranchOut,
    CaseFormDataOut,
    CaseTrailIn,
)
from chatddx.repo.entities.client.django import ClientBranchModel
from chatddx.repo.entities.client.pydantic import (
    ClientBranchDetailsPatch,
    ClientBranchOut,
    ClientFormDataOut,
    ClientTrailIn,
)
from chatddx.repo.entities.coercion.django import CoercionBranchModel
from chatddx.repo.entities.coercion.pydantic import (
    CoercionBranchOut,
    CoercionFormDataOut,
    CoercionTrailIn,
)
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.configuration.pydantic import (
    ConfigurationBranchOut,
    ConfigurationFormDataOut,
    ConfigurationTrailIn,
)
from chatddx.repo.entities.instruction.django import InstructionBranchModel
from chatddx.repo.entities.instruction.pydantic import (
    InstructionBranchOut,
    InstructionFormDataOut,
    InstructionTrailIn,
)
from chatddx.repo.entities.machine.django import MachineBranchModel
from chatddx.repo.entities.machine.pydantic import (
    MachineBranchDetailsPatch,
    MachineBranchOut,
    MachineFormDataOut,
    MachineTrailIn,
)
from chatddx.repo.entities.model.django import ModelBranchModel
from chatddx.repo.entities.model.pydantic import (
    ModelBranchDetailsPatch,
    ModelBranchOut,
    ModelFormDataOut,
    ModelTrailIn,
)
from chatddx.repo.entities.os.django import OsBranchModel
from chatddx.repo.entities.os.pydantic import (
    OsBranchDetailsPatch,
    OsBranchOut,
    OsFormDataOut,
    OsTrailIn,
)
from chatddx.repo.entities.output.django import OutputBranchModel
from chatddx.repo.entities.output.pydantic import (
    OutputBranchOut,
    OutputFormDataOut,
    OutputTrailIn,
)
from chatddx.repo.entities.reasoning.django import ReasoningBranchModel
from chatddx.repo.entities.reasoning.pydantic import (
    ReasoningBranchOut,
    ReasoningFormDataOut,
    ReasoningTrailIn,
)
from chatddx.repo.entities.sampling.django import SamplingBranchModel
from chatddx.repo.entities.sampling.pydantic import (
    SamplingBranchOut,
    SamplingFormDataOut,
    SamplingTrailIn,
)
from chatddx.repo.entities.scorer.django import ScorerBranchModel
from chatddx.repo.entities.scorer.pydantic import (
    ScorerBranchDetailsPatch,
    ScorerBranchOut,
    ScorerFormDataOut,
    ScorerTrailIn,
)
from chatddx.repo.entities.serving.django import ServingBranchModel
from chatddx.repo.entities.serving.pydantic import (
    ServingBranchDetailsPatch,
    ServingBranchOut,
    ServingFormDataOut,
    ServingTrailIn,
)
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.entities.stack.pydantic import (
    StackBranchDetailsPatch,
    StackBranchOut,
    StackFormDataOut,
    StackTrailIn,
)
from chatddx.repo.entities.tool.django import ToolBranchModel
from chatddx.repo.entities.tool.pydantic import (
    ToolBranchDetailsPatch,
    ToolBranchOut,
    ToolFormDataOut,
    ToolTrailIn,
)
from chatddx.repo.entities.toolset.django import ToolsetBranchModel
from chatddx.repo.entities.toolset.pydantic import (
    ToolsetBranchOut,
    ToolsetFormDataOut,
    ToolsetTrailIn,
)
from chatddx.repo.families.pydantic import BranchDetailsPatch


class ParsedInventory(BaseModel):
    # a record's content, and what its branch says beside it
    machine: dict[str, tuple[MachineTrailIn, MachineBranchDetailsPatch]]
    os: dict[str, tuple[OsTrailIn, OsBranchDetailsPatch]]
    model: dict[str, tuple[ModelTrailIn, ModelBranchDetailsPatch]]
    serving: dict[str, tuple[ServingTrailIn, ServingBranchDetailsPatch]]
    client: dict[str, tuple[ClientTrailIn, ClientBranchDetailsPatch]]
    stack: dict[str, tuple[StackTrailIn, StackBranchDetailsPatch]]
    tool: dict[str, tuple[ToolTrailIn, ToolBranchDetailsPatch]]
    toolset: dict[str, tuple[ToolsetTrailIn, BranchDetailsPatch]]
    instruction: dict[str, tuple[InstructionTrailIn, BranchDetailsPatch]]
    output: dict[str, tuple[OutputTrailIn, BranchDetailsPatch]]
    coercion: dict[str, tuple[CoercionTrailIn, BranchDetailsPatch]]
    reasoning: dict[str, tuple[ReasoningTrailIn, BranchDetailsPatch]]
    sampling: dict[str, tuple[SamplingTrailIn, BranchDetailsPatch]]
    configuration: dict[str, tuple[ConfigurationTrailIn, BranchDetailsPatch]]
    case: dict[str, tuple[CaseTrailIn, CaseBranchDetailsPatch]]
    scorer: dict[str, tuple[ScorerTrailIn, ScorerBranchDetailsPatch]]


class InventoryTrailIn(BaseModel):
    machine: dict[str, MachineTrailIn]
    os: dict[str, OsTrailIn]
    model: dict[str, ModelTrailIn]
    serving: dict[str, ServingTrailIn]
    client: dict[str, ClientTrailIn]
    stack: dict[str, StackTrailIn]
    tool: dict[str, ToolTrailIn]
    toolset: dict[str, ToolsetTrailIn]
    instruction: dict[str, InstructionTrailIn]
    output: dict[str, OutputTrailIn]
    coercion: dict[str, CoercionTrailIn]
    reasoning: dict[str, ReasoningTrailIn]
    sampling: dict[str, SamplingTrailIn]
    configuration: dict[str, ConfigurationTrailIn]
    case: dict[str, CaseTrailIn]
    scorer: dict[str, ScorerTrailIn]


class InventoryFormDataOut(BaseModel):
    machine: dict[str, MachineFormDataOut]
    os: dict[str, OsFormDataOut]
    model: dict[str, ModelFormDataOut]
    serving: dict[str, ServingFormDataOut]
    client: dict[str, ClientFormDataOut]
    stack: dict[str, StackFormDataOut]
    tool: dict[str, ToolFormDataOut]
    toolset: dict[str, ToolsetFormDataOut]
    instruction: dict[str, InstructionFormDataOut]
    output: dict[str, OutputFormDataOut]
    coercion: dict[str, CoercionFormDataOut]
    reasoning: dict[str, ReasoningFormDataOut]
    sampling: dict[str, SamplingFormDataOut]
    configuration: dict[str, ConfigurationFormDataOut]
    case: dict[str, CaseFormDataOut]
    scorer: dict[str, ScorerFormDataOut]


class InventoryBranchOut(BaseModel):
    machine: dict[str, MachineBranchOut]
    os: dict[str, OsBranchOut]
    model: dict[str, ModelBranchOut]
    serving: dict[str, ServingBranchOut]
    client: dict[str, ClientBranchOut]
    stack: dict[str, StackBranchOut]
    tool: dict[str, ToolBranchOut]
    toolset: dict[str, ToolsetBranchOut]
    instruction: dict[str, InstructionBranchOut]
    output: dict[str, OutputBranchOut]
    coercion: dict[str, CoercionBranchOut]
    reasoning: dict[str, ReasoningBranchOut]
    sampling: dict[str, SamplingBranchOut]
    configuration: dict[str, ConfigurationBranchOut]
    case: dict[str, CaseBranchOut]
    scorer: dict[str, ScorerBranchOut]


class InventoryBranchModel(TypedDict):
    machine: dict[str, MachineBranchModel]
    os: dict[str, OsBranchModel]
    model: dict[str, ModelBranchModel]
    serving: dict[str, ServingBranchModel]
    client: dict[str, ClientBranchModel]
    stack: dict[str, StackBranchModel]
    tool: dict[str, ToolBranchModel]
    toolset: dict[str, ToolsetBranchModel]
    instruction: dict[str, InstructionBranchModel]
    output: dict[str, OutputBranchModel]
    coercion: dict[str, CoercionBranchModel]
    reasoning: dict[str, ReasoningBranchModel]
    sampling: dict[str, SamplingBranchModel]
    configuration: dict[str, ConfigurationBranchModel]
    case: dict[str, CaseBranchModel]
    scorer: dict[str, ScorerBranchModel]
