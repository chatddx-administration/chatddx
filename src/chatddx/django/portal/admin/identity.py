# pyright: basic
from django.contrib import admin

from chatddx.core.proxies import Identity
from chatddx.django.portal.admin.base import TypedModelAdmin


@admin.register(Identity)
class IdentityAdmin(TypedModelAdmin[Identity]):
    list_display = [
        "name",
        "auth_user",
        "guest_id",
    ]
    fields = list_display + [
        "secrets",
    ]
    readonly_fields = ["guest_id"]
