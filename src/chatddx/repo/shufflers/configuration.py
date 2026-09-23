from typing import cast

from django.db.models import QuerySet

from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.configuration.pydantic import ConfigurationBranchSpec
from chatddx.repo.families.django import BranchModel
from chatddx.repo.shufflers.branch import (
    get_branch_spec,
    select_branch_specs,
)
from chatddx.utils import make_async


def get_configuration(
    owner_name: str,
    branch_name: str,
    qs: QuerySet[ConfigurationBranchModel] | None = None,
) -> ConfigurationBranchSpec:
    configuration = get_branch_spec(
        entity_name="configuration",
        owner_name=owner_name,
        branch_name=branch_name,
        qs=cast(QuerySet[BranchModel], qs),
    )

    return cast(ConfigurationBranchSpec, configuration)


get_configuration_async = make_async(get_configuration)


def select_configurations(
    owner_name: str,
    qs: QuerySet[ConfigurationBranchModel] | None = None,
) -> list[ConfigurationBranchSpec]:
    configurations = select_branch_specs(
        entity_name="configuration",
        owner_name=owner_name,
        qs=cast(QuerySet[BranchModel], qs),
    )
    return cast(list[ConfigurationBranchSpec], configurations)


select_configurations_async = make_async(select_configurations)
