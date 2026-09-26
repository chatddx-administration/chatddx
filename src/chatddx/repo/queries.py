from collections.abc import Sequence
from typing import Any

from django.db.models import Count, OuterRef, Prefetch, Q, QuerySet, Subquery

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel
from chatddx.repo.utils import trail_paths

type AnyBranch = BranchModel | BranchProxy


def qs_owned[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    return qs.filter(owner__name=owner_name)


def qs_head[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
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


def deleted(model: BranchModel) -> bool:
    """Whether the row says its timeline is deleted: as its head, it is."""
    return model.details.get("deleted") is True


def deleted_timelines(models: Sequence[BranchModel]) -> set[tuple[int, str]]:
    """
    The timelines, by owner and name, of those of `models` whose head is
    deleted: a row goes with its timeline, head or not.
    """
    wanted = {(model.owner_id, model.name) for model in models}

    if not wanted:
        return set()

    model_cls = type(models[0])
    heads = (
        model_cls.objects.filter(
            owner_id__in={owner for owner, _ in wanted},
            name__in={name for _, name in wanted},
        )
        .order_by("owner_id", "name", "-timestamp", "-id")
        .distinct("owner_id", "name")
        .values_list("owner_id", "name", "details")
    )

    return {
        (owner, name)
        for owner, name, details in heads
        if (owner, name) in wanted and details.get("deleted") is True
    }


def live_first[T: BranchModel](models: Sequence[T]) -> list[T]:
    """
    `models`, less the rows of a deleted timeline whose owner has a live one
    among them: a deleted branch gives way to a live one of its owner's, and
    stands, for what it held, where its owner has no other.
    """
    gone = deleted_timelines(models)
    live = {
        model.owner_id for model in models if (model.owner_id, model.name) not in gone
    }

    return [
        model
        for model in models
        if (model.owner_id, model.name) not in gone or model.owner_id not in live
    ]


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
