from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from chatddx.history.schemas import SessionSpec
from chatddx.repo.entities.agent.pydantic import AgentTrailSpec

OutputType = bool | int | str | Decimal | list[Any] | dict[str, Any]


@dataclass(frozen=True)
class AgentContext:
    agent: AgentTrailSpec
    output_type: type[OutputType] | None = None
    session: SessionSpec | None = None
