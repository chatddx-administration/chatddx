# pyright: basic

from django.contrib import admin

from chatddx.django.portal.branch import BranchModelAdmin
from chatddx.django.portal.forms.output_type import OutputTypeForm
from chatddx.repo.entities.output_type.django import OutputType


@admin.register(OutputType)
class OutputTypeAdmin(BranchModelAdmin[OutputType]):
    form = OutputTypeForm
    name = "output_type"

    list_display = list(BranchModelAdmin.list_display) + [
        "name",
        "_type",
        "validation_strategy",
        "coercion_strategy",
    ]

    @admin.display(
        description="Coercion Strategy",
        ordering="target__coercion_strategy",
    )
    def coercion_strategy(self, obj: OutputType) -> str:
        return obj.target.get_coercion_strategy_display()  # pyright: ignore[reportAttributeAccessIssue]

    @admin.display(
        description="Type",
        ordering="target__definition",
    )
    def _type(self, obj: OutputType) -> str:
        return obj.target.definition.get("type", None)  # pyright: ignore[reportAttributeAccessIssue]

    @admin.display(
        description="Validation Strategy",
        ordering="target__validation_strategy",
    )
    def validation_strategy(self, obj: OutputType) -> str:
        return obj.target.get_validation_strategy_display()  # pyright: ignore
