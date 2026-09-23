# pyright: basic
from __future__ import annotations

from typing import Any

from django.db.models import (
    PROTECT,
    CharField,
    DateTimeField,
    Field,
    ForeignKey,
    Index,
    ManyToManyField,
    Model,
)

from chatddx.core.models import IdentityModel, TagModel


class TrailModel(Model):
    id: int

    branch_name: str | None = None

    fingerprint = CharField(
        max_length=64,
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
        short_hash = self.fingerprint[:6]
        return self.branch_name or short_hash


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
