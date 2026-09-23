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
    """
    A JSON document kept as it was written. Postgres' jsonb re-sorts an
    object's keys, and the order of a schema's keys is what a constrained
    decoder emits and what a model shown the schema reads, so a document whose
    order carries meaning is stored as text (new-datamodel.md §10).
    """

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

    # `cddx-trail/1:sha256:<64 hex digits>`, which outgrew 64 characters
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

    def __str__(self) -> str:
        return self.branch_name or short_fingerprint(self.fingerprint)


class BranchModel(Model):
    id: int

    target: Field[Any, Any]
    target_id: int

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

    # What the entity's details schema says beside its content and its
    # relations: a machine's specs, a stack's endpoint. It is written once per
    # version, like `target`; a change to it makes a new version.
    details: JSONField[dict[str, Any]] = JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        abstract = True
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
    target: TrailModel
    version_count: int | None = None

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.name
