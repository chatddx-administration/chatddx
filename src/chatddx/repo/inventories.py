"""
An inventory: every entity's records by name, in one of the forms a record
takes on its way from an inventory file to the database and back.
"""

from typing import TypedDict

from pydantic import BaseModel

from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import (
    CaseBranchDetailsPatch,
    CaseBranchSpec,
    CaseFormDataOut,
    CaseTrailSchema,
)
from chatddx.repo.entities.client.django import ClientBranchModel
from chatddx.repo.entities.client.pydantic import (
    ClientBranchDetailsPatch,
    ClientBranchSpec,
    ClientFormDataOut,
    ClientTrailSchema,
)
from chatddx.repo.entities.coercion.django import CoercionBranchModel
from chatddx.repo.entities.coercion.pydantic import (
    CoercionBranchSpec,
    CoercionFormDataOut,
    CoercionTrailSchema,
)
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.configuration.pydantic import (
    ConfigurationBranchSpec,
    ConfigurationFormDataOut,
    ConfigurationTrailSchema,
)
from chatddx.repo.entities.instruction.django import InstructionBranchModel
from chatddx.repo.entities.instruction.pydantic import (
    InstructionBranchSpec,
    InstructionFormDataOut,
    InstructionTrailSchema,
)
from chatddx.repo.entities.machine.django import MachineBranchModel
from chatddx.repo.entities.machine.pydantic import (
    MachineBranchDetailsPatch,
    MachineBranchSpec,
    MachineFormDataOut,
    MachineTrailSchema,
)
from chatddx.repo.entities.model.django import ModelBranchModel
from chatddx.repo.entities.model.pydantic import (
    ModelBranchDetailsPatch,
    ModelBranchSpec,
    ModelFormDataOut,
    ModelTrailSchema,
)
from chatddx.repo.entities.os.django import OsBranchModel
from chatddx.repo.entities.os.pydantic import (
    OsBranchDetailsPatch,
    OsBranchSpec,
    OsFormDataOut,
    OsTrailSchema,
)
from chatddx.repo.entities.output.django import OutputBranchModel
from chatddx.repo.entities.output.pydantic import (
    OutputBranchSpec,
    OutputFormDataOut,
    OutputTrailSchema,
)
from chatddx.repo.entities.reasoning.django import ReasoningBranchModel
from chatddx.repo.entities.reasoning.pydantic import (
    ReasoningBranchSpec,
    ReasoningFormDataOut,
    ReasoningTrailSchema,
)
from chatddx.repo.entities.sampling.django import SamplingBranchModel
from chatddx.repo.entities.sampling.pydantic import (
    SamplingBranchSpec,
    SamplingFormDataOut,
    SamplingTrailSchema,
)
from chatddx.repo.entities.scorer.django import ScorerBranchModel
from chatddx.repo.entities.scorer.pydantic import (
    ScorerBranchDetailsPatch,
    ScorerBranchSpec,
    ScorerFormDataOut,
    ScorerTrailSchema,
)
from chatddx.repo.entities.serving.django import ServingBranchModel
from chatddx.repo.entities.serving.pydantic import (
    ServingBranchDetailsPatch,
    ServingBranchSpec,
    ServingFormDataOut,
    ServingTrailSchema,
)
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.entities.stack.pydantic import (
    StackBranchDetailsPatch,
    StackBranchSpec,
    StackFormDataOut,
    StackTrailSchema,
)
from chatddx.repo.entities.tool.django import ToolBranchModel
from chatddx.repo.entities.tool.pydantic import (
    ToolBranchDetailsPatch,
    ToolBranchSpec,
    ToolFormDataOut,
    ToolTrailSchema,
)
from chatddx.repo.entities.toolset.django import ToolsetBranchModel
from chatddx.repo.entities.toolset.pydantic import (
    ToolsetBranchSpec,
    ToolsetFormDataOut,
    ToolsetTrailSchema,
)
from chatddx.repo.families.pydantic import BranchDetailsPatch


class ParsedInventory(BaseModel):
    # a record's content, and what its branch says beside it
    machine: dict[str, tuple[MachineTrailSchema, MachineBranchDetailsPatch]]
    os: dict[str, tuple[OsTrailSchema, OsBranchDetailsPatch]]
    model: dict[str, tuple[ModelTrailSchema, ModelBranchDetailsPatch]]
    serving: dict[str, tuple[ServingTrailSchema, ServingBranchDetailsPatch]]
    client: dict[str, tuple[ClientTrailSchema, ClientBranchDetailsPatch]]
    stack: dict[str, tuple[StackTrailSchema, StackBranchDetailsPatch]]
    tool: dict[str, tuple[ToolTrailSchema, ToolBranchDetailsPatch]]
    toolset: dict[str, tuple[ToolsetTrailSchema, BranchDetailsPatch]]
    instruction: dict[str, tuple[InstructionTrailSchema, BranchDetailsPatch]]
    output: dict[str, tuple[OutputTrailSchema, BranchDetailsPatch]]
    coercion: dict[str, tuple[CoercionTrailSchema, BranchDetailsPatch]]
    reasoning: dict[str, tuple[ReasoningTrailSchema, BranchDetailsPatch]]
    sampling: dict[str, tuple[SamplingTrailSchema, BranchDetailsPatch]]
    configuration: dict[str, tuple[ConfigurationTrailSchema, BranchDetailsPatch]]
    case: dict[str, tuple[CaseTrailSchema, CaseBranchDetailsPatch]]
    scorer: dict[str, tuple[ScorerTrailSchema, ScorerBranchDetailsPatch]]


class InventoryTrailSchema(BaseModel):
    machine: dict[str, MachineTrailSchema]
    os: dict[str, OsTrailSchema]
    model: dict[str, ModelTrailSchema]
    serving: dict[str, ServingTrailSchema]
    client: dict[str, ClientTrailSchema]
    stack: dict[str, StackTrailSchema]
    tool: dict[str, ToolTrailSchema]
    toolset: dict[str, ToolsetTrailSchema]
    instruction: dict[str, InstructionTrailSchema]
    output: dict[str, OutputTrailSchema]
    coercion: dict[str, CoercionTrailSchema]
    reasoning: dict[str, ReasoningTrailSchema]
    sampling: dict[str, SamplingTrailSchema]
    configuration: dict[str, ConfigurationTrailSchema]
    case: dict[str, CaseTrailSchema]
    scorer: dict[str, ScorerTrailSchema]


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


class InventoryBranchSpec(BaseModel):
    machine: dict[str, MachineBranchSpec]
    os: dict[str, OsBranchSpec]
    model: dict[str, ModelBranchSpec]
    serving: dict[str, ServingBranchSpec]
    client: dict[str, ClientBranchSpec]
    stack: dict[str, StackBranchSpec]
    tool: dict[str, ToolBranchSpec]
    toolset: dict[str, ToolsetBranchSpec]
    instruction: dict[str, InstructionBranchSpec]
    output: dict[str, OutputBranchSpec]
    coercion: dict[str, CoercionBranchSpec]
    reasoning: dict[str, ReasoningBranchSpec]
    sampling: dict[str, SamplingBranchSpec]
    configuration: dict[str, ConfigurationBranchSpec]
    case: dict[str, CaseBranchSpec]
    scorer: dict[str, ScorerBranchSpec]


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
