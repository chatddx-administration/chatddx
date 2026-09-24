# pyright: basic
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.models import (
    PROTECT,
    CharField,
    ForeignKey,
    JSONField,
    Model,
    OneToOneField,
    UniqueConstraint,
    UUIDField,
)
from encrypted_fields import EncryptedJSONField


class IdentityModel(Model):
    class Meta:
        app_label = "core"
        db_table = "core_identity"
        ordering = ("name",)

    def __str__(self):
        return self.name

    name = CharField(
        max_length=255,
        unique=True,
    )
    secrets: JSONField[Any] = EncryptedJSONField(default=dict)
    guest_id = UUIDField(
        default=None,
        null=True,
        blank=True,
    )
    auth_user = OneToOneField(
        settings.AUTH_USER_MODEL,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
    )


class Identity(IdentityModel):
    class Meta:
        app_label = "core"
        proxy = True
        verbose_name = "Identity"
        verbose_name_plural = "Identities"

    def __str__(self):
        return self.name


class TagModel(Model):
    class Meta:
        app_label = "core"
        db_table = "core_tag"
        ordering = ("name",)
        constraints = (
            UniqueConstraint(
                fields=["owner", "name", "entity"],
                name="unique_tag_per_owner_and_entity",
            ),
        )

    def __str__(self):
        return self.name

    owner_id: int
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
        related_name="tags",
    )

    entity = CharField(
        max_length=255,
    )

    name = CharField(
        max_length=255,
    )
