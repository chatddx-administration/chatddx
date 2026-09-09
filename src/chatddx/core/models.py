from typing import Any

from django.conf import settings
from django.db.models import (
    PROTECT,
    CharField,
    ForeignKey,
    Model,
    OneToOneField,
    UniqueConstraint,
    UUIDField,
)
from encrypted_fields import EncryptedJSONField


class IdentityModel(Model):
    class Meta:
        app_label = "orm"
        db_table = "agents_identity"

    def __str__(self):
        return self.name

    name = CharField(
        max_length=255,
        unique=True,
    )
    secrets: dict[str, Any] = EncryptedJSONField(default=dict)  # type: ignore[assignment]
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


class TagModel(Model):
    class Meta:
        app_label = "orm"
        db_table = "agents_tag"
        constraints = [
            UniqueConstraint(fields=["owner", "name"], name="unique_tag_per_owner"),
        ]

    def __str__(self):
        return self.name

    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
        related_name="tags",
    )
    # Django synthesizes this alongside `owner`, but django-types doesn't
    # model that.
    owner_id: int
    name = CharField(
        max_length=255,
    )
