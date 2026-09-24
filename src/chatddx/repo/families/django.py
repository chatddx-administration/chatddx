# pyright: basic
from __future__ import annotations

import json
from typing import Any

from django.db.models import (
    PROTECT,
    CharField,
    DateTimeField,
    Field,
    ForeignKey,
    Index,
    JSONField,
    ManyToManyField,
    Model,
    TextField,
)

from chatddx.core.models import IdentityModel, TagModel
from chatddx.repo.names import short_fingerprint


class OrderedJSONField(TextField):
    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:
        return None if value is None else json.loads(value)

    def to_python(self, value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    def get_prep_value(self, value: Any) -> Any:
        return None if value is None else json.dumps(value, ensure_ascii=False)

    def value_to_string(self, obj: Model) -> str:
        return json.dumps(self.value_from_object(obj), ensure_ascii=False)


class TrailModel(Model):
    id: int

    branch_name: str | None = None

    fingerprint = CharField(
        max_length=128,
        db_index=True,
        editable=False,
        unique=True,
    )
    timestamp = DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        abstract = True
        app_label = "orm"

    def __str__(self) -> str:
        return self.branch_name or short_fingerprint(self.fingerprint)


class BranchModel(Model):
    id: int

    trail: Field[Any, Any]
    trail_id: int

    version_count: int | None = None

    name = CharField(max_length=255)

    timestamp = DateTimeField(
        auto_now_add=True,
    )

    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
        related_name="owned_%(class)s",
    )
    owner_id: int

    collaborators: ManyToManyField[IdentityModel, Any] = ManyToManyField(
        IdentityModel,
        blank=True,
        related_name="shared_%(class)s",
    )

    tags: ManyToManyField[TagModel, Any] = ManyToManyField(
        TagModel,
        blank=True,
        related_name="tagged_%(class)s",
    )

    details: JSONField[dict[str, Any]] = JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        abstract = True
        app_label = "orm"
        indexes = (Index(fields=["owner", "name", "-timestamp"]),)

    def as_proxy[ModelT: Model](self, proxy_model: type[ModelT]) -> ModelT:
        fields = self._meta.fields
        return proxy_model.from_db(
            db=self._state.db,
            field_names=[f.name for f in fields],
            values=[getattr(self, f.name) for f in fields],
        )


class BranchProxy(Model):
    pk: int
    name: str
    trail: TrailModel
    version_count: int | None = None

    class Meta:
        app_label = "orm"
        abstract = True

    def __str__(self) -> str:
        return self.name
