from typing import cast

from django.db.models import QuerySet

from chatddx.repo.entities.agent.django import AgentBranchModel
from chatddx.repo.entities.agent.pydantic import AgentBranchSpec
from chatddx.repo.families.django import BranchModel
from chatddx.repo.shufflers.branch import (
    get_branch_spec,
    select_branch_specs,
)
from chatddx.utils import make_async


def get_agent(
    owner_name: str,
    branch_name: str,
    qs: QuerySet[AgentBranchModel] | None = None,
) -> AgentBranchSpec:

    agent = get_branch_spec(
        entity_name="agent",
        owner_name=owner_name,
        branch_name=branch_name,
        qs=cast(QuerySet[BranchModel], qs),
    )

    return cast(AgentBranchSpec, agent)


get_agent_async = make_async(get_agent)


def select_agents(
    owner_name: str,
    qs: QuerySet[AgentBranchModel] | None = None,
) -> list[AgentBranchSpec]:

    agents = select_branch_specs(
        entity_name="agent",
        owner_name=owner_name,
        qs=cast(QuerySet[BranchModel], qs),
    )
    return cast(list[AgentBranchSpec], agents)


select_agents_async = make_async(select_agents)
