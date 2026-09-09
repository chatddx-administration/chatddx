from __future__ import annotations

from chatddx.django.orm.qs import qs_canon
from chatddx.repo.branch_models import ScorerBranchModel
from chatddx.repo.shufflers.main import ensure_identity
from chatddx.repo.trail_models import ScorerTrailModel
from chatddx.repo.trail_schemas import ScorerSchema
from chatddx.utils import make_async

DEFAULT_SCORER_NAMES = [
    "chatddx.experiment.scorers.exact_match",
    "chatddx.experiment.scorers.regex_match",
]


def dump_scorer(name: str, owner_name: str) -> tuple[ScorerBranchModel, bool]:
    schema = ScorerSchema(name=name)

    owner = ensure_identity(owner_name)

    canon = qs_canon(
        ScorerBranchModel.objects.filter(name=name),
        owner.name,
    ).first()

    if canon and schema.fingerprint == canon.target.fingerprint:
        return canon, False

    trail, _ = ScorerTrailModel.objects.get_or_create(
        fingerprint=schema.fingerprint,
        defaults={"name": schema.name},
    )

    branch = ScorerBranchModel.objects.create(
        target=trail,
        owner=owner,
        name=name,
    )

    return branch, True


dump_scorer_async = make_async(dump_scorer)


def dump_scorers(
    names: list[str],
    owner_name: str,
) -> dict[int, ScorerBranchModel]:
    dumped: dict[int, ScorerBranchModel] = {}

    for name in names:
        branch, _ = dump_scorer(name, owner_name)
        dumped[branch.pk] = branch

    return dumped


dump_scorers_async = make_async(dump_scorers)
