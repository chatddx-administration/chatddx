# pyright: basic
"""The registry as the identity sees it, entity by entity, in the repo's schemas."""

from django.db.models import prefetch_related_objects
from django.http import HttpRequest
from ninja import Query, Router

from chatddx.bench.bench import Bench
from chatddx.django.api.identity import identity_of
from chatddx.django.api.schemas import Detail, Page, RunSummary
from chatddx.django.api.showing import detail_of, summary_of
from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import ENTITY_NAMES, EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.store.branch import get_shared_branch_model, get_visible_branch_model
from chatddx.repo.utils import resolve_trails
from chatddx.scoring.score import Scoring

router = Router(tags=["registry"])


def named(
    bench: Bench, entity: EntityName, name: str, owner: str | None
) -> BranchModel:
    if owner is not None:
        return get_shared_branch_model(entity, bench.identity, owner, name)

    if entity == "configuration":
        return bench.configuration_named(name)

    return get_visible_branch_model(entity, bench.identity, name)


def _routes(entity: EntityName) -> None:
    out = entity_of(entity).branch_out

    def branches(request: HttpRequest, tag: Query[list[str] | None] = None):
        bench = Bench(identity_of(request))
        found = bench.tagged(entity, tag) if tag else bench.usable(entity)
        prefetch_related_objects(found, "collaborators")
        return found

    def branch(request: HttpRequest, name: str, owner: str | None = None):
        bench = Bench(identity_of(request))
        return detail_of(bench, entity, named(bench, entity, name, owner))

    def versions(request: HttpRequest, name: str, owner: str | None = None):
        bench = Bench(identity_of(request))
        head = named(bench, entity, name, owner)
        rows = entity_of(entity).branch_model.objects.filter(
            owner=head.owner, name=head.name
        )

        if head.owner.name != bench.identity:
            rows = rows.filter(collaborators__name=bench.identity)

        found = list(
            rows.select_related("owner", "trail").order_by("-timestamp", "-pk")
        )
        _ = resolve_trails([row.trail for row in found])
        return found

    def runs(
        request: HttpRequest, name: str, page: Query[Page], owner: str | None = None
    ):
        bench = Bench(identity_of(request))
        found = bench.runs_with(entity, named(bench, entity, name, owner).trail_id)
        scoring = Scoring(bench.identity)
        return [
            summary_of(run, scoring)
            for run in found[page.offset : page.offset + page.limit]
        ]

    for path, view, response, summary in (
        ("", branches, list[out], f"Each {entity} the identity can use, or any tag's"),
        (
            "/{name}",
            branch,
            Detail[out],
            f"The {entity} NAME, or owner's, and its runs",
        ),
        ("/{name}/versions", versions, list[out], "Its versions, the head first"),
        ("/{name}/runs", runs, list[RunSummary], "The identity's runs with it"),
    ):
        router.add_api_operation(
            f"/{entity}{path}",
            ["GET"],
            view,
            response=response,
            operation_id=f"{entity}_{view.__name__}",
            summary=summary,
        )


for _entity in ENTITY_NAMES:
    _routes(_entity)
