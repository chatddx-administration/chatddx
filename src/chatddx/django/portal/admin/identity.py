# pyright: basic
from typing import Any

from django.contrib import admin
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

from chatddx.core.proxies import Identity
from chatddx.django.portal.admin.base import TypedModelAdmin

# Members of this group only ever manage their own identity: the changelist
# redirects them straight to its change form instead of listing every
# identity.
RESTRICTED_GROUP_NAME = "users"


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

    def _restrict_to_own_identity(self, request: HttpRequest) -> bool:
        user = request.user
        return (
            not user.is_superuser
            and user.groups.filter(name=RESTRICTED_GROUP_NAME).exists()
        )

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)

        if self._restrict_to_own_identity(request):
            return qs.filter(name=request.user.username)

        return qs

    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ):
        if self._restrict_to_own_identity(request):
            own_identity = self.get_queryset(request).first()

            if own_identity is not None:
                return HttpResponseRedirect(
                    reverse("admin:orm_identity_change", args=(own_identity.pk,))
                )

        return super().changelist_view(request, extra_context)
