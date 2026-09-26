# pyright: basic
"""The registry as the identity sees it: configurations, stacks, cases, show NAME."""

from django.http import HttpRequest
from ninja import Query, Router

from chatddx.django.api.identity import identity_of
from chatddx.django.api.schemas import Branch, BranchDetail, Page, RunSummary
from chatddx.django.api.showing import branches_of, detail_of, summary_of
from chatddx.repl.bench import Bench
from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.store.branch import get_shared_branch_model, get_visible_branch_model
from chatddx.repo.utils import resolve_trails
from chatddx.scoring.score import Scoring

router = Router(tags=["registry"])


@router.get("/{entity}", response=list[Branch])
def branches(
    request: HttpRequest, entity: EntityName, tag: Query[list[str] | None] = None
):
    """The head of each branch of ENTITY the identity can use: all, or any `tag`'s."""
    bench = Bench(identity_of(request))
    models = bench.tagged(entity, tag) if tag else bench.usable(entity)

    return branches_of(bench, entity, models)


@router.get("/{entity}/{name}", response=BranchDetail)
def branch(
    request: HttpRequest, entity: EntityName, name: str, owner: str | None = None
):
    """The branch the identity means by NAME, or `owner`'s, and its runs with it."""
    bench = Bench(identity_of(request))
    return detail_of(bench, entity, named(bench, entity, name, owner))


@router.get("/{entity}/{name}/versions", response=list[Branch])
def versions(
    request: HttpRequest, entity: EntityName, name: str, owner: str | None = None
):
    """The branch's versions the identity can see, the head first."""
    bench = Bench(identity_of(request))
    head = named(bench, entity, name, owner)
    rows = entity_of(entity).branch_model.objects.filter(
        owner=head.owner, name=head.name
    )

    if head.owner.name != bench.identity:
        rows = rows.filter(collaborators__name=bench.identity)

    found = list(rows.select_related("owner", "trail").order_by("-timestamp", "-pk"))
    _ = resolve_trails([row.trail for row in found])

    return branches_of(bench, entity, found)


@router.get("/{entity}/{name}/runs", response=list[RunSummary])
def runs(
    request: HttpRequest,
    entity: EntityName,
    name: str,
    page: Query[Page],
    owner: str | None = None,
):
    """The identity's runs with the branch's trail, the latest first."""
    bench = Bench(identity_of(request))
    model = named(bench, entity, name, owner)
    found = bench.runs_with(entity, model.trail_id)
    scoring = Scoring(bench.identity)

    return [
        summary_of(run, scoring)
        for run in found[page.offset : page.offset + page.limit]
    ]


def named(
    bench: Bench, entity: EntityName, name: str, owner: str | None
) -> BranchModel:
    if owner is not None:
        return get_shared_branch_model(entity, bench.identity, owner, name)

    if entity == "configuration":
        return bench.configuration_named(name)

    return get_visible_branch_model(entity, bench.identity, name)
