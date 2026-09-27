# pyright: basic
"""
The sampling variations' pages: the owner's variations, what each leaves to
its defaults and what it sets outright; and a variation's own page, as each
slice's is (variation_admin), showing what the variation does on each LLM
the owner's stacks serve, reasoning each way its facts realize.
"""

from typing import Any, override

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from chatddx.django.portal import samplings
from chatddx.django.portal.forms import SAMPLING_SET, SamplingForm
from chatddx.django.portal.models import Sampling
from chatddx.django.portal.records import said
from chatddx.django.portal.variation_admin import VariationAdmin

# what the portal calls a sampling, for the model holds no words of the portal's
Sampling._meta.verbose_name = _("sampling variation")
Sampling._meta.verbose_name_plural = _("sampling variations")


class SamplingAdmin(VariationAdmin):
    entity = "sampling"
    variation_form = SamplingForm
    page_template = "portal/sampling/page.html"
    said_template = "portal/sampling/said.html"
    list_display = ("name_", "defaults_", "sets_", "versions_", "saved_")

    @admin.display(description=_("A setting left out"))
    def defaults_(self, sampling: Sampling) -> str:
        return sampling.trail.defaults

    @admin.display(description=_("Sets outright"))
    def sets_(self, sampling: Sampling) -> str:
        trail = sampling.trail
        sets = {
            name: getattr(trail, name)
            for name in (*SAMPLING_SET, "stop")
            if getattr(trail, name) is not None
        }

        return said(sets) if sets else "—"

    @override
    def shown_of(self, owner: str, trail: Any) -> dict[str, Any]:
        return {
            "realized": None if trail is None else samplings.realized_on(owner, trail)
        }
