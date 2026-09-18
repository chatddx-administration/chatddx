from dataclasses import dataclass
from typing import Literal

from chatddx.repo.entities.agent import (
    Agent as AgentProxy,
    # 8 entries redacted
    AgentTrailSpec,
)

# 8 entries redacted
from chatddx.repo.families import (
    BaseFormDataIn,
    # 8 entries redacted
    TrailSpec,
)

type EntityName = Literal[
    "agent",
    # 8 entries redacted
    "super_agent",
]


@dataclass(frozen=True)
class Bundle[
    BS: BranchSchema,
    # 8 entries redacted
    P: BranchProxy,
]:
    name: EntityName
    branch_schema: type[BS]
    # 8 entries redacted
    proxy: type[P]

    def members(self) -> tuple[type, ...]:
        return (
            self.branch_schema,
            # 8 entries redacted
            self.proxy,
        )


type AnyBundle = Bundle[
    BranchSchema,
    # 8 entries redacted
    BranchProxy,
]

type AnyMember = (
    BranchSchema | BranchSpec | TrailSchema | TrailSpec | TrailSchemaRef | object
)

type SuperAgentBundle = Bundle[
    AgentBranchSchema,
    # 8 entries redacted
    SuperAgentProxy,
]
type SuperAgentMember = (
    AgentBranchSchema
    # 8 entries redacted
    | SuperAgentProxy
)

SUPER_AGENT: SuperAgentBundle = Bundle(
    name="agent",
    # 8 entries redacted
    proxy=SuperAgentProxy,
)

# 8 entries redacted

type ExpectBundle = Bundle[
    ExpectBranchSchema,
    # 8 entries redacted
    ExpectProxy,
]
type ExpectMember = (
    ExpectBranchSchema
    # 8 entries redacted
    | ExpectProxy
)

EXPECT: ExpectBundle = Bundle(
    name="expect",
    # 8 entries redacted
    proxy=ExpectProxy,
)


ALL_BUNDLES: tuple[AnyBundle, ...] = (
    AGENT,
    # 8 entries redacted
    SUPER_AGENT,
)
