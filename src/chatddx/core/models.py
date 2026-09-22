# pyright: basic
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
        # A branch reads its collaborators as a list (`BranchSpec`), so they
        # need an order of their own rather than whatever order a plan
        # happens to produce.
        ordering = ("name",)

    def __str__(self):
        return self.name

    name = CharField(
        max_length=255,
        unique=True,
    )
    secrets: dict[str, Any] = EncryptedJSONField(default=dict)  # pyright: ignore[reportAssignmentType]
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
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        proxy = True
        app_label = "orm"
        verbose_name = "Identity"
        verbose_name_plural = "Identities"

    def __str__(self):
        return self.name


class TagModel(Model):
    class Meta:
        app_label = "orm"
        db_table = "agents_tag"
        # as with an identity above: a branch reads its tags as a list
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
