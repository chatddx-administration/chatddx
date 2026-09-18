# src/chatddx/repo/inventories.py

from typing import TypedDict

from pydantic import BaseModel

from chatddx.repo.entities.agent.django import AgentBranchModel
from chatddx.repo.entities.agent.pydantic import (
    AgentBranchSpec,
    AgentFormDataOut,
    AgentTrailSchema,
)
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import (
    CaseBranchSpec,
    CaseFormDataOut,
    CaseTrailSchema,
)
from chatddx.repo.entities.connection.django import ConnectionBranchModel
from chatddx.repo.entities.connection.pydantic import (
    ConnectionBranchSpec,
    ConnectionFormDataOut,
    ConnectionTrailSchema,
)
from chatddx.repo.entities.expect.django import ExpectBranchModel
from chatddx.repo.entities.expect.pydantic import (
    ExpectBranchSpec,
    ExpectFormDataOut,
    ExpectTrailSchema,
)
from chatddx.repo.entities.output_type.django import OutputTypeBranchModel
from chatddx.repo.entities.output_type.pydantic import (
    OutputTypeBranchSpec,
    OutputTypeFormDataOut,
    OutputTypeTrailSchema,
)
from chatddx.repo.entities.sampling_params.django import SamplingParamsBranchModel
from chatddx.repo.entities.sampling_params.pydantic import (
    SamplingParamsBranchSpec,
    SamplingParamsFormDataOut,
    SamplingParamsTrailSchema,
)
from chatddx.repo.entities.scorer.django import ScorerBranchModel
from chatddx.repo.entities.scorer.pydantic import (
    ScorerBranchSpec,
    ScorerFormDataOut,
    ScorerTrailSchema,
)
from chatddx.repo.entities.super_agent.pydantic import SuperAgentFormDataOut
from chatddx.repo.entities.tool.django import ToolBranchModel
from chatddx.repo.entities.tool.pydantic import (
    ToolBranchSpec,
    ToolFormDataOut,
    ToolTrailSchema,
)
from chatddx.repo.entities.tool_group.django import ToolGroupBranchModel
from chatddx.repo.entities.tool_group.pydantic import (
    ToolGroupBranchSpec,
    ToolGroupFormDataOut,
    ToolGroupTrailSchema,
)
from chatddx.repo.families.pydantic import BranchDetailsPatch


class ParsedInventory(BaseModel):
    agent: dict[str, tuple[AgentTrailSchema, BranchDetailsPatch]]
    connection: dict[str, tuple[ConnectionTrailSchema, BranchDetailsPatch]]
    sampling_params: dict[str, tuple[SamplingParamsTrailSchema, BranchDetailsPatch]]
    tool_group: dict[str, tuple[ToolGroupTrailSchema, BranchDetailsPatch]]
    tool: dict[str, tuple[ToolTrailSchema, BranchDetailsPatch]]
    output_type: dict[str, tuple[OutputTypeTrailSchema, BranchDetailsPatch]]
    case: dict[str, tuple[CaseTrailSchema, BranchDetailsPatch]]
    scorer: dict[str, tuple[ScorerTrailSchema, BranchDetailsPatch]]
    expect: dict[str, tuple[ExpectTrailSchema, BranchDetailsPatch]]
    super_agent: dict[str, tuple[AgentTrailSchema, BranchDetailsPatch]]


class InventoryTrailSchema(BaseModel):
    agent: dict[str, AgentTrailSchema]
    connection: dict[str, ConnectionTrailSchema]
    sampling_params: dict[str, SamplingParamsTrailSchema]
    tool_group: dict[str, ToolGroupTrailSchema]
    tool: dict[str, ToolTrailSchema]
    output_type: dict[str, OutputTypeTrailSchema]
    case: dict[str, CaseTrailSchema]
    scorer: dict[str, ScorerTrailSchema]
    expect: dict[str, ExpectTrailSchema]
    super_agent: dict[str, AgentTrailSchema]


class InventoryFormDataOut(BaseModel):
    agent: dict[str, AgentFormDataOut]
    connection: dict[str, ConnectionFormDataOut]
    sampling_params: dict[str, SamplingParamsFormDataOut]
    output_type: dict[str, OutputTypeFormDataOut]
    tool_group: dict[str, ToolGroupFormDataOut]
    tool: dict[str, ToolFormDataOut]
    case: dict[str, CaseFormDataOut]
    scorer: dict[str, ScorerFormDataOut]
    expect: dict[str, ExpectFormDataOut]
    super_agent: dict[str, SuperAgentFormDataOut]


class InventoryBranchSpec(BaseModel):
    agent: dict[str, AgentBranchSpec]
    connection: dict[str, ConnectionBranchSpec]
    sampling_params: dict[str, SamplingParamsBranchSpec]
    output_type: dict[str, OutputTypeBranchSpec]
    tool_group: dict[str, ToolGroupBranchSpec]
    tool: dict[str, ToolBranchSpec]
    case: dict[str, CaseBranchSpec]
    scorer: dict[str, ScorerBranchSpec]
    expect: dict[str, ExpectBranchSpec]
    super_agent: dict[str, AgentBranchSpec]


class InventoryBranchModel(TypedDict):
    agent: dict[str, AgentBranchModel]
    connection: dict[str, ConnectionBranchModel]
    sampling_params: dict[str, SamplingParamsBranchModel]
    output_type: dict[str, OutputTypeBranchModel]
    tool_group: dict[str, ToolGroupBranchModel]
    tool: dict[str, ToolBranchModel]
    case: dict[str, CaseBranchModel]
    scorer: dict[str, ScorerBranchModel]
    expect: dict[str, ExpectBranchModel]
    super_agent: dict[str, AgentBranchModel]
