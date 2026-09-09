# src/chatddx/core/django_fields.py
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.postgres.fields.array import ArrayField
from django.db.models import ForeignKey, JSONField, OneToOneField

from chatddx.utils import make_async

if TYPE_CHECKING:
    from chatddx.repo.base import TrailModel

    TypedJSONField = JSONField[dict[str, Any]]
    TypedArrayField = ArrayField[list[int]]
else:
    TypedJSONField = JSONField
    TypedArrayField = ArrayField


class JSONSchemaField(TypedJSONField):
    pass


class RelatedArrayField(TypedArrayField):
    def __init__(
        self,
        *args: Any,
        associated_model: type["TrailModel"],
        **kwargs: Any,
    ) -> None:
        self.associated_model: type["TrailModel"] = associated_model
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["associated_model"] = self.associated_model
        return name, path, args, kwargs


def resolve_related_array_fields(model: TrailModel):
    for field in model._meta.concrete_fields:
        if isinstance(field, RelatedArrayField):
            value = getattr(model, field.name)

            if not value:
                setattr(model, field.name, [])
                continue

            queryset = field.associated_model.objects.filter(pk__in=value)
            resolved_value = list(queryset)

            for obj in resolved_value:
                _ = resolve_related_array_fields(obj)

            setattr(model, field.name, resolved_value)

        elif isinstance(field, (ForeignKey, OneToOneField)):
            associated_model = getattr(model, field.name, None)
            if associated_model is not None:
                _ = resolve_related_array_fields(associated_model)

    return model


resolve_related_array_fields_async = make_async(resolve_related_array_fields)
