# pyright: basic
from django.contrib import admin

from chatddx.django.portal.admin.base import BranchModelAdmin
from chatddx.django.portal.forms import (
    OutputTypeForm,
)
from chatddx.repo import proxies


@admin.register(proxies.OutputType)
class OutputTypeAdmin(BranchModelAdmin[proxies.OutputType]):
    form = OutputTypeForm
    name = "output_type"

    list_display = BranchModelAdmin.list_display + [  # pyright: ignore
        "name",
        "_type",
        "validation_strategy",
        "coercion_strategy",
    ]

    @admin.display(
        description="Coercion Strategy",
        ordering="target__coercion_strategy",
    )
    def coercion_strategy(self, obj: proxies.OutputType) -> str:
        return obj.target.get_coercion_strategy_display()  # pyright: ignore

    @admin.display(
        description="Type",
        ordering="target__definition",
    )
    def _type(self, obj: proxies.OutputType) -> str:
        return obj.target.definition.get("type", None)  # pyright: ignore

    @admin.display(
        description="Validation Strategy",
        ordering="target__validation_strategy",
    )
    def validation_strategy(self, obj: proxies.OutputType) -> str:
        return obj.target.get_validation_strategy_display()  # pyright: ignore
