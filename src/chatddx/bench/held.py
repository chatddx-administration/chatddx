from collections.abc import Collection
from dataclasses import dataclass, field

from chatddx.history.models import RunModel, ScoreModel, TrialModel
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.configuration.django import (
    ConfigurationBranchModel,
    ConfigurationTrailModel,
)
from chatddx.repo.entities.configuration.pydantic import SLICES
from chatddx.repo.entity_names import EntityName
from chatddx.repo.queries import reaching
from chatddx.worker.models import JobModel


@dataclass(frozen=True)
class Held:
    runs: int = 0
    jobs: int = 0
    scores: int = 0
    configurations: list[ConfigurationBranchModel] = field(
        default_factory=list[ConfigurationBranchModel]
    )

    def __bool__(self) -> bool:
        return bool(self.runs or self.jobs or self.scores or self.configurations)


def held(
    owner: str,
    entity: EntityName,
    trails: Collection[int],
    branches: Collection[int] = (),
) -> Held:
    trail_model = entity_of(entity).trail_model
    through = reaching(TrialModel, trail_model, trails, through="trial")

    return Held(
        runs=RunModel.objects.filter(owner__name=owner).filter(through).count(),
        jobs=JobModel.objects.filter(owner__name=owner).filter(through).count(),
        scores=(
            ScoreModel.objects.filter(case_branch__in=list(branches)).count()
            if branches
            else 0
        ),
        configurations=(
            list(
                ConfigurationBranchModel.objects.filter(owner__name=owner)
                .filter(reaching(ConfigurationTrailModel, trail_model, trails, "trail"))
                .select_related("owner", "trail")
                .order_by("name", "timestamp", "id")
            )
            if entity in SLICES
            else []
        ),
    )
