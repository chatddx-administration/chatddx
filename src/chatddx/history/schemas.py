from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ninja import Schema as NinjaSchema
from pydantic import BaseModel
from pydantic_ai import ModelRequest, ModelResponse

from chatddx.core.choices import MessageKindChoices, RoleChoices, SessionContextChoices
from chatddx.repo.entities.agent.pydantic import AgentBranchSchema, AgentBranchSpec


class SessionBase(BaseModel):
    uuid: UUID
    description: str | None
    context: SessionContextChoices
    timestamp: datetime
    owner_id: int


class SessionSchema(SessionBase):
    default_agent: AgentBranchSchema


class SessionSpec(SessionBase, NinjaSchema):
    id: int
    default_agent: AgentBranchSpec
    messages: list[MessageSpec]


class PromptPayload(BaseModel):
    content: str


class ErrorPayload(BaseModel):
    error_type: str
    content: str


class MessageSpec(NinjaSchema):
    id: int
    agent_id: int
    session_id: int
    role: RoleChoices
    run_id: UUID
    kind: MessageKindChoices
    payload: ModelRequest | ModelResponse | PromptPayload | ErrorPayload
    timestamp: datetime
