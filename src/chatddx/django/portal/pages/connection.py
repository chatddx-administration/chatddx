# pyright: basic

from django.contrib import admin

from chatddx.django.portal.branch import BranchModelAdmin
from chatddx.django.portal.forms.connection import ConnectionForm
from chatddx.repo.entities.connection.django import Connection


@admin.register(Connection)
class ConnectionAdmin(BranchModelAdmin[Connection]):
    form = ConnectionForm
    name = "connection"

    list_display = list(BranchModelAdmin.list_display) + [
        "name",
        "_model",
        "provider",
        "endpoint",
    ]

    @admin.display(description="Model", ordering="target__model")
    def _model(self, obj: Connection) -> str:
        return obj.target.model  # pyright: ignore[reportAttributeAccessIssue]

    @admin.display(description="Endpoint", ordering="target__endpoint")
    def endpoint(self, obj: Connection) -> str:
        return obj.target.endpoint  # pyright: ignore[reportAttributeAccessIssue]

    @admin.display(description="Provider", ordering="target__provider")
    def provider(self, obj: Connection) -> str:
        return obj.target.get_provider_display()  # pyright: ignore[reportAttributeAccessIssue]
