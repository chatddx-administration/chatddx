from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self, overload

from django.db.models import F, Model, OuterRef, QuerySet, Subquery
from django.utils.safestring import SafeString

from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel

type AnyBranch = BranchModel | BranchProxy


@dataclass(frozen=True)
class BranchOf[P: BranchProxy]:
    trail: TrailModel
    id: int | None
    name: str | None
    entity: EntityName
    proxy: type[P]

    @property
    def label(self) -> TrailModel:
        self.trail.branch_name = self.name

        return self.trail

    def link(self, **params: Any) -> SafeString:
        from chatddx.django.portal.links import add_link, change_link

        if self.id is not None:
            return change_link(self.proxy(pk=self.id), self.label, **params)

        return add_link(
            self.proxy,
            self.label,
            **params,
            **{f"{self.entity}_fingerprint": self.trail.fingerprint},
        )


class BranchRef[P: BranchProxy]:
    def __init__(
        self,
        trail_path: str,
        entity: EntityName,
        proxy: type[P],
    ) -> None:
        self.trail_path: str = trail_path
        self.entity: EntityName = entity
        self.proxy: type[P] = proxy
        self.attname: str = ""

    def __set_name__(self, owner: type[Model], name: str) -> None:
        self.attname = name

    @property
    def id_alias(self) -> str:
        return f"{self.attname}_id"

    @property
    def name_alias(self) -> str:
        return f"{self.attname}_name"

    @overload
    def __get__(self, obj: None, objtype: type[Model] | None = None) -> Self: ...

    @overload
    def __get__(
        self, obj: Model, objtype: type[Model] | None = None
    ) -> BranchOf[P]: ...

    def __get__(
        self,
        obj: Model | None,
        objtype: type[Model] | None = None,
    ) -> Self | BranchOf[P]:
        if obj is None:
            return self

        return BranchOf(
            trail=self.trail_of(obj),
            id=self._annotated(obj, self.id_alias),
            name=self._annotated(obj, self.name_alias),
            entity=self.entity,
            proxy=self.proxy,
        )

    @property
    def branch_model(self) -> type[BranchModel]:
        assert issubclass(self.proxy, BranchModel)

        return self.proxy

    def trail_of(self, obj: Model) -> TrailModel:
        value: Any = obj

        for step in self.trail_path.split("__"):
            value = getattr(value, step)

        assert isinstance(value, TrailModel)

        return value

    def _annotated(self, obj: Model, alias: str) -> Any:
        try:
            return obj.__dict__[alias]
        except KeyError:
            raise AttributeError(
                f"{type(obj).__name__}.{alias} is not on this row. "
                + f"{self.attname!r} is put there by annotate_branch_refs(), "
                + "which this queryset did not go through."
            ) from None


def branch_refs(model_cls: type[Model]) -> dict[str, BranchRef[Any]]:
    refs: dict[str, BranchRef[Any]] = {}

    for klass in reversed(model_cls.__mro__):
        for name, value in vars(klass).items():
            if isinstance(value, BranchRef):
                refs[name] = value

    return refs


def annotate_branch_refs[T: Model](
    qs: QuerySet[T],
    owner_name: str,
    *only: str,
) -> QuerySet[T]:
    refs = branch_refs(qs.model)

    if only:
        refs = {name: refs[name] for name in only}

    if not refs:
        return qs

    annotations: dict[str, Subquery] = {}

    for ref in refs.values():
        branch_qs = ref.branch_model.objects.filter(
            target=OuterRef(ref.trail_path),
            owner__name=owner_name,
        ).order_by("-timestamp")

        annotations[ref.id_alias] = Subquery(branch_qs.values("id")[:1])
        annotations[ref.name_alias] = Subquery(branch_qs.values("name")[:1])

    return qs.select_related(*(ref.trail_path for ref in refs.values())).annotate(
        **annotations
    )


def annotate_branch_name[T: TrailModel](qs: QuerySet[T], field: str) -> QuerySet[T]:
    return qs.annotate(branch_name=F(field))
