from django.db.models import ForeignKey, OneToOneField

from chatddx.core.django_fields import RelatedArrayField
from chatddx.repo.families.django import TrailModel
from chatddx.utils import make_async


def resolve_trail(model: TrailModel):
    for field in model._meta.concrete_fields:
        if isinstance(field, RelatedArrayField):
            value = getattr(model, field.name)

            if not value:
                setattr(model, field.name, [])
                continue

            pks = [r.pk if isinstance(r, TrailModel) else r for r in value]

            queryset = field.associated_model.objects.filter(pk__in=pks)

            resolved_value = list(queryset)

            for obj in resolved_value:
                _ = resolve_trail(obj)

            setattr(model, field.name, resolved_value)

        elif isinstance(field, (ForeignKey, OneToOneField)):
            associated_model = getattr(model, field.name, None)
            if associated_model is not None:
                _ = resolve_trail(associated_model)

    return model


resolve_trail_async = make_async(resolve_trail)


def trail_relations(model: TrailModel) -> list[TrailModel]:
    """
    The trails `model` points at directly.

    sibling walk in `resolve_trail` above: the same two kinds of field, read
    rather than written back onto the model.
    """
    related: list[TrailModel] = []

    for field in model._meta.concrete_fields:
        if isinstance(field, RelatedArrayField):
            value = getattr(model, field.name)

            if not value:
                continue

            pks = [r.pk if isinstance(r, TrailModel) else r for r in value]

            related.extend(field.associated_model.objects.filter(pk__in=pks))

        elif isinstance(field, (ForeignKey, OneToOneField)):
            associated_model = getattr(model, field.name, None)

            # a trail only ever points at trails, but nothing stops one from
            # pointing elsewhere, and that is not part of its closure
            if isinstance(associated_model, TrailModel):
                related.append(associated_model)

    return related


def trail_closure(model: TrailModel) -> list[TrailModel]:
    """
    Every trail `model` reaches, nearest first, `model` itself excluded.

    What a trail points at is its content -- an agent *is* its connection,
    sampling params, output type and tool group, and a tool group is its
    tools -- so this is the rest of the thing the fingerprint stands for.

    The walk terminates because the graph cannot have a cycle: a
    fingerprint covers the fingerprints of what it points at, so a cycle
    would have to contain its own hash.
    """
    seen = {(model._meta.concrete_model, model.pk)}
    queue = [model]
    closure: list[TrailModel] = []

    while queue:
        for related in trail_relations(queue.pop(0)):
            key = (related._meta.concrete_model, related.pk)

            if key in seen:
                continue

            seen.add(key)
            closure.append(related)
            queue.append(related)

    return closure


trail_closure_async = make_async(trail_closure)
