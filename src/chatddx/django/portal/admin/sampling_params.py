# pyright: basic
from django.contrib import admin

from chatddx.django.portal.admin.base import BranchModelAdmin
from chatddx.django.portal.forms import SamplingParamsForm
from chatddx.repo import proxies


@admin.register(proxies.SamplingParams)
class SamplingParamsAdmin(BranchModelAdmin[proxies.SamplingParams]):
    form = SamplingParamsForm
    name = "sampling_params"

    list_display = BranchModelAdmin.list_display + [  # pyright: ignore
        "name",
        "seed",
        "temperature",
        "top_p",
    ]

    @admin.display(description="Seed", ordering="target__seed")
    def seed(self, obj: proxies.SamplingParams) -> str:
        return str(obj.target.seed)  # pyright: ignore

    @admin.display(description="Temp", ordering="target__temperature")
    def temperature(self, obj: proxies.SamplingParams) -> str:
        return str(obj.target.temperature)  # pyright: ignore

    @admin.display(description="Top-p", ordering="target__top_p")
    def top_p(self, obj: proxies.SamplingParams) -> str:
        return str(obj.target.top_p)  # pyright: ignore
