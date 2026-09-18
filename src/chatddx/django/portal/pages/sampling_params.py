# pyright: basic
from django.contrib import admin

from chatddx.django.portal.branch import BranchModelAdmin
from chatddx.django.portal.forms.sampling_params import SamplingParamsForm
from chatddx.repo.entities.sampling_params.django import SamplingParams


@admin.register(SamplingParams)
class SamplingParamsAdmin(BranchModelAdmin[SamplingParams]):
    form = SamplingParamsForm
    name = "sampling_params"

    list_display = list(BranchModelAdmin.list_display) + [
        "name",
        "seed",
        "temperature",
        "top_p",
    ]

    @admin.display(description="Seed", ordering="target__seed")
    def seed(self, obj: SamplingParams) -> str:
        return str(obj.target.seed)  # pyright: ignore[reportAttributeAccessIssue]

    @admin.display(description="Temp", ordering="target__temperature")
    def temperature(self, obj: SamplingParams) -> str:
        return str(obj.target.temperature)  # pyright: ignore[reportAttributeAccessIssue]

    @admin.display(description="Top-p", ordering="target__top_p")
    def top_p(self, obj: SamplingParams) -> str:
        return str(obj.target.top_p)  # pyright: ignore[reportAttributeAccessIssue]
