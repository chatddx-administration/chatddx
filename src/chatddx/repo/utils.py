from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any, cast

from django.db.models import ForeignKey, OneToOneField

from chatddx.core.django_fields import RelatedArrayField
from chatddx.repo.families.django import TrailModel
from chatddx.utils import make_async

type _TrailFK = ForeignKey[TrailModel]

type _Key = tuple[type[TrailModel] | None, Any]


def _key(model: TrailModel) -> _Key:
    return (model._meta.concrete_model, model.pk)


def _array_fields(model_cls: type[TrailModel]) -> list[RelatedArrayField]:
    """The fields of `model_cls` that hold a list of trails as ids."""
    return [
        field
        for field in model_cls._meta.concrete_fields
        if isinstance(field, RelatedArrayField)
    ]


def _relation_fields(model_cls: type[TrailModel]) -> list[_TrailFK]:
    relations: list[_TrailFK] = []

    for field in model_cls._meta.concrete_fields:
        if not isinstance(field, (ForeignKey, OneToOneField)):
            continue

        related = cast(type[Any], field.related_model)

        if issubclass(related, TrailModel):
            relations.append(cast(_TrailFK, field))

    return relations


def _resolve_array(
    field: RelatedArrayField,
    rows: Sequence[TrailModel],
) -> list[TrailModel]:
    named: dict[int, list[Any]] = {}
    wanted: set[Any] = set()
    resolved: list[TrailModel] = []

    for row in rows:
        value: list[Any] = list(getattr(row, field.name) or [])

        if all(isinstance(item, TrailModel) for item in value):
            setattr(row, field.name, value)
            resolved += value
            continue

        pks = [item.pk if isinstance(item, TrailModel) else item for item in value]
        named[id(row)] = pks
        wanted.update(pks)

    by_pk: dict[Any, TrailModel] = (
        field.associated_model.objects.in_bulk(wanted) if wanted else {}
    )

    for row in rows:
        if id(row) not in named:
            continue

        setattr(row, field.name, [by_pk[pk] for pk in named[id(row)] if pk in by_pk])

    return resolved + list(by_pk.values())


def _resolve_relation(
    field: _TrailFK,
    rows: Sequence[TrailModel],
) -> list[TrailModel]:
    pending = [row for row in rows if not field.is_cached(row)]
    wanted = {getattr(row, field.attname) for row in pending} - {None}

    by_pk: dict[Any, TrailModel] = (
        field.related_model.objects.in_bulk(wanted) if wanted else {}
    )

    for row in pending:
        related = by_pk.get(getattr(row, field.attname))
        if related is not None:
            field.set_cached_value(row, related)

    reached: list[TrailModel] = []

    for row in rows:
        related = field.get_cached_value(row, default=None)

        if isinstance(related, TrailModel):
            reached.append(related)

    return reached


def trail_paths(model_cls: type[TrailModel], prefix: str = "") -> list[str]:
    paths: list[str] = []

    for field in _relation_fields(model_cls):
        path = f"{prefix}{field.name}"
        paths.append(path)
        paths += trail_paths(field.related_model, f"{path}__")

    return paths


def resolve_trails[T: TrailModel](models: Sequence[T]) -> list[T]:
    level: list[TrailModel] = list(models)

    seen: dict[int, TrailModel] = {id(model): model for model in level}

    while level:
        by_class: dict[type[TrailModel], list[TrailModel]] = defaultdict(list)

        for model in level:
            by_class[type(model)].append(model)

        reached: list[TrailModel] = []

        for model_cls, rows in by_class.items():
            for array in _array_fields(model_cls):
                reached += _resolve_array(array, rows)

            for relation in _relation_fields(model_cls):
                reached += _resolve_relation(relation, rows)

        level = []

        for model in reached:
            if id(model) in seen:
                continue

            seen[id(model)] = model
            level.append(model)

    return list(models)


def resolve_trail[T: TrailModel](model: T) -> T:
    return resolve_trails([model])[0]


resolve_trail_async = make_async(resolve_trail)
resolve_trails_async = make_async(resolve_trails)


def trail_relations(model: TrailModel) -> list[TrailModel]:
    related: list[TrailModel] = []

    for field in _array_fields(type(model)):
        value: Iterable[Any] = getattr(model, field.name) or []
        pks = [item.pk if isinstance(item, TrailModel) else item for item in value]

        if pks:
            related.extend(field.associated_model.objects.filter(pk__in=pks))

    for field in _relation_fields(type(model)):
        associated_model = getattr(model, field.name, None)

        if isinstance(associated_model, TrailModel):
            related.append(associated_model)

    return related


def trail_closure(model: TrailModel) -> list[TrailModel]:
    seen: set[_Key] = {_key(model)}
    queue: list[TrailModel] = [model]
    closure: list[TrailModel] = []

    while queue:
        for related in trail_relations(queue.pop(0)):
            if _key(related) in seen:
                continue

            seen.add(_key(related))
            closure.append(related)
            queue.append(related)

    return closure


trail_closure_async = make_async(trail_closure)
