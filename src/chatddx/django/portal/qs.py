from collections import defaultdict
from typing import Any

from django.db.models import Count, OuterRef, Prefetch, Q, QuerySet, Subquery

from chatddx.history.models import BatchModel, ExperimentModel
from chatddx.history.proxies import Message
from chatddx.repo.entities.case.django import CaseExpect
from chatddx.repo.families.branch_refs import (
    AnyBranch,
    annotate_branch_name,
    annotate_branch_refs,
)
from chatddx.repo.families.django import BranchModel, TrailModel
from chatddx.repo.utils import trail_paths


def qs_owned[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    return qs.filter(owner__name=owner_name)


def qs_head[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    return _head(qs, qs_owned(qs, owner_name))


def qs_head_visible[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
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

    return (
        owned.filter(id__in=canonical_ids)
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


def qs_super_agent[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    return annotate_branch_refs(qs_with_trail(qs), owner_name)


def qs_messages(qs: QuerySet[Message], owner_name: str) -> QuerySet[Message]:
    return annotate_branch_refs(qs, owner_name).order_by("timestamp")


def qs_experiments(
    qs: QuerySet[ExperimentModel],
    owner_name: str,
) -> QuerySet[ExperimentModel]:
    return annotate_branch_refs(qs, owner_name)


def qs_batches(qs: QuerySet[BatchModel], owner_name: str) -> QuerySet[BatchModel]:
    return annotate_branch_refs(qs, owner_name)


# --------------------------------------------------------------- trails


def qs_owned_trails[T: TrailModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    return (
        annotate_branch_name(
            qs.filter(branches__owner__name=owner_name),
            "branches__name",
        )
        .order_by("id")
        .distinct("id")
    )


def expects_by_case(owner_name: str) -> dict[int, list[int]]:
    links = (
        CaseExpect.objects.filter(case__owner__name=owner_name)
        .values_list("case__target_id", "expect__target_id")
        .distinct()
    )

    by_case: dict[int, list[int]] = defaultdict(list)

    for case_trail_id, expect_trail_id in links:
        by_case[case_trail_id].append(expect_trail_id)

    return {case_id: sorted(expect_ids) for case_id, expect_ids in by_case.items()}
