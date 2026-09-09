# pyright: basic

from django.contrib import admin

from chatddx.django.portal.admin.base import BranchModelAdmin
from chatddx.django.portal.forms import ConnectionForm
from chatddx.repo import proxies


@admin.register(proxies.Connection)
class ConnectionAdmin(BranchModelAdmin[proxies.Connection]):
    form = ConnectionForm
    name = "connection"

    list_display = BranchModelAdmin.list_display + [  # pyright: ignore
        "name",
        "_model",
        "provider",
        "endpoint",
    ]

    @admin.display(description="Model", ordering="target__model")
    def _model(self, obj: proxies.Connection) -> str:
        return obj.target.model  # pyright: ignore

    @admin.display(description="Endpoint", ordering="target__endpoint")
    def endpoint(self, obj: proxies.Connection) -> str:
        return obj.target.endpoint  # pyright: ignore

    @admin.display(description="Provider", ordering="target__provider")
    def provider(self, obj: proxies.Connection) -> str:
        return obj.target.get_provider_display()  # pyright: ignore
