from typing import Any

from django.conf import settings
from django.db.models import PROTECT, CharField, Model, OneToOneField, UUIDField
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
    """A plain label a branch (currently: case branches) can be marked with.

    Tags are not repo-matter: there is no trail/branch pair for a tag and no
    central tag-management surface. This is just a lookup table plus
    whatever many-to-many relations branch models declare against it, used
    to find the branches -- and through them, the trail currently
    associated with each -- carrying a given label.
    """

    class Meta:
        app_label = "orm"
        db_table = "agents_tag"

    def __str__(self):
        return self.name

    name = CharField(
        max_length=255,
        unique=True,
    )
