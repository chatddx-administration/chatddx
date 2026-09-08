# src/chatddx/core/django_fields.py
from typing import TYPE_CHECKING, Any

from django.contrib.postgres.fields.array import ArrayField
from django.db.models import JSONField

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
