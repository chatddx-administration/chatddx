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
    Manager,
    ManyToManyField,
    Model,
)

from chatddx.core.models import IdentityModel, TagModel


class TrailModel(Model):
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

    def __str__(self):
        name = getattr(self, "branch_name", None)
        short_hash = self.fingerprint[:6]
        return f"{name} ({short_hash})" if name else short_hash


class BranchModel(Model):
    target: Field[Any, Any]

    name = CharField(max_length=255)

    timestamp = DateTimeField(
        auto_now_add=True,
    )

    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
        related_name="owned_%(class)s",
    )

    collaborators = ManyToManyField(
        IdentityModel,
        blank=True,
        related_name="shared_%(class)s",
    )

    tags = ManyToManyField(
        TagModel,
        blank=True,
        related_name="tagged_%(class)s",
    )

    class Meta:
        abstract = True
        indexes = (Index(fields=["owner", "name", "-timestamp"]),)

    def as_proxy(self, proxy_model):
        return proxy_model.from_db(
            db=self._state.db,
            field_names=[f.name for f in self._meta.fields],
            values=[getattr(self, f.name) for f in self._meta.fields],
        )


class BranchProxy:
    pk: int
    name: str
    objects: Manager[BranchModel]
    target: TrailModel

    def __str__(self) -> str:
        return self.name
