# src/chatddx/experiment/schemas.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ninja import Schema as NinjaSchema
from pydantic import BaseModel, field_validator

from chatddx.repo.trail_schemas import (
    AgentSchema,
    CaseSchema,
    ExpectSchema,
    ScorerSchema,
)
from chatddx.repo.trail_specs import AgentSpec, CaseSpec, ExpectSpec, ScorerSpec


class ExperimentBase(BaseModel):
    uuid: UUID
    timestamp: datetime
    owner_id: int
    tags: list[str] = []

    @field_validator("tags", mode="before")
    @classmethod
    def _split_tags(cls, value: object) -> object:
        if isinstance(value, str):
            return [tag.strip() for tag in value.split(",") if tag.strip()]
        return value


class ExperimentSchema(ExperimentBase):
    agent: AgentSchema
    case: CaseSchema
    expect: ExpectSchema
    scorer: ScorerSchema | None = None


class ExperimentSpec(ExperimentBase, NinjaSchema):
    id: int
    agent: AgentSpec
    case: CaseSpec
    expect: ExpectSpec
    scorer: ScorerSpec | None = None
