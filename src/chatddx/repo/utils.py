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
