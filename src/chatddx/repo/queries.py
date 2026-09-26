"""
The queries the registry answers itself: an owner's heads, and a branch with
what it carries.

`chatddx.django.portal.qs` builds the portal's pages on these; the registry
doesn't reach up for them, so it stands without the pages.
"""

from typing import Any

from django.db.models import Count, OuterRef, Prefetch, Q, QuerySet, Subquery

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel
from chatddx.repo.utils import trail_paths

type AnyBranch = BranchModel | BranchProxy


def qs_owned[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    return qs.filter(owner__name=owner_name)


def qs_head[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    """The newest version of each of `owner_name`'s branches."""
    return _head(qs, qs_owned(qs, owner_name))


def head_of[T: BranchModel](qs: QuerySet[T], owner_name: str, name: str) -> T | None:
    """The head of `owner_name`'s branch `name`, as `qs_head` has it, if it has one."""
    return (
        qs_owned(qs, owner_name)
        .filter(name=name)
        .select_related("owner", "trail")
        .order_by("-timestamp", "-id")
        .first()
    )


def qs_head_visible[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    """As `qs_head`, with the branches `owner_name` collaborates on."""
    return _head(
        qs,
        qs.filter(Q(owner__name=owner_name) | Q(collaborators__name=owner_name)),
    )


def _head[T: BranchModel](qs: QuerySet[T], owned: QuerySet[T]) -> QuerySet[T]:
    version_count = (
        qs.filter(owner_id=OuterRef("owner_id"), name=OuterRef("name"))
        .values("owner_id", "name")
        .annotate(total=Count("id"))
        .values("total")
    )

    canonical_ids = (
        owned.order_by("owner_id", "name", "-timestamp", "-id")
        .distinct("owner_id", "name")
        .values_list("id", flat=True)
    )

    # the heads by id alone: joined to the collaborators `owned` is filtered
    # on, a branch would come once for each
    return (
        qs.filter(id__in=canonical_ids)
        .select_related("owner", "trail")
        .annotate(version_count=Subquery(version_count))
        .order_by("-timestamp")
    )


def qs_with_trail[T: AnyBranch](qs: QuerySet[T]) -> QuerySet[T]:
    paths = trail_paths(_trail_model(qs), "trail__")
    return qs.select_related(*paths) if paths else qs


def qs_with_relations[T: AnyBranch](qs: QuerySet[T]) -> QuerySet[T]:
    prefetch: list[str | Prefetch[Any]] = []

    for m2m in qs.model._meta.many_to_many:
        related = m2m.related_model

        if issubclass(related, BranchModel):
            prefetch.append(
                Prefetch(m2m.name, queryset=qs_with_relations(related.objects.all()))
            )
        else:
            prefetch.append(m2m.name)

    return qs_with_trail(qs).select_related("owner").prefetch_related(*prefetch)


def _trail_model(qs: QuerySet[AnyBranch]) -> type[TrailModel]:
    related = qs.model._meta.get_field("trail").related_model

    assert related is not None and issubclass(related, TrailModel)

    return related
