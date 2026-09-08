from typing import Any

from pydantic import field_validator

from chatddx.repo.base import BranchSpec
from chatddx.repo.trail_specs import (
    AgentSpec,
    CaseSpec,
    ConnectionSpec,
    OutputTypeSpec,
    SamplingParamsSpec,
    ToolGroupSpec,
    ToolSpec,
)


class CaseBranchSpec(BranchSpec[CaseSpec]):
    target: CaseSpec
    # Tags live on CaseBranchModel, not the (fingerprinted) trail, so they
    # sit here rather than on CaseSpec/CaseBase -- same reasoning as
    # BranchBase.collaborators. NinjaSchema resolves the M2M manager to
    # TagModel instances (see ninja.schema.DjangoGetter); pull out the pks
    # the form actually wants.
    tags: list[int] = []

    @field_validator("tags", mode="before")
    @classmethod
    def _tag_pks(cls, value: list[Any]) -> list[int]:
        return [item if isinstance(item, int) else item.pk for item in value]


class ConnectionBranchSpec(BranchSpec[ConnectionSpec]):
    target: ConnectionSpec


class SamplingParamsBranchSpec(BranchSpec[SamplingParamsSpec]):
    target: SamplingParamsSpec


class OutputTypeBranchSpec(BranchSpec[OutputTypeSpec]):
    target: OutputTypeSpec


class ToolBranchSpec(BranchSpec[ToolSpec]):
    target: ToolSpec


class ToolGroupBranchSpec(BranchSpec[ToolGroupSpec]):
    target: ToolGroupSpec


class AgentBranchSpec(BranchSpec[AgentSpec]):
    target: AgentSpec
