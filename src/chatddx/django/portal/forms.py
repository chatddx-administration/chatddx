# pyright: basic
"""
The Batch form: the repl's cell and batch, with its slices varied. Use and On
put a configuration and a stack in the cell, the case tags say which cases it
runs on, the variations ticked on each slice are crossed into the batch's
cells, and the seed is each trial's, a greedy cell's aside.
"""

import json
from math import prod
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from unfold.widgets import (
    UnfoldAdminIntegerFieldWidget,
    UnfoldAdminSelect2MultipleWidget,
    UnfoldAdminSelect2Widget,
)

from chatddx.bench.bench import MAX_SEED, Bench, drawn_seed
from chatddx.bench.cell import NONE, OPTIONAL, SLICES
from chatddx.bench.plan import Plan, crossed
from chatddx.core.models import IdentityModel
from chatddx.django.portal import batches
from chatddx.django.portal.models import Batch
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel

# the most cells a batch crosses its variations into
MOST_CELLS = 100


class HeardSelect2MultipleWidget(UnfoldAdminSelect2MultipleWidget):
    """
    Unfold's select2 multiple, its choice told to the form's Alpine data as
    unfold tells it a select2 single's: select2 tells jQuery, not the DOM.
    """

    def get_context(self, name: str, value: Any, attrs: Any) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        attrs = context["widget"]["attrs"]
        attrs["x-init"] = (
            "const $ = django.jQuery; $(function () { "
            + f"const select = $('#{attrs['id']}'); "
            + f"select.on('change', () => {{ {name} = select.val(); }}); }});"
        )
        return context


class ChipsWidget(forms.CheckboxSelectMultiple):
    """A slice's few variations, as a row of chips to tick."""

    template_name = "portal/widgets/chips.html"
    option_template_name = "portal/widgets/chip.html"


def variations_field(slice_: str) -> forms.MultipleChoiceField:
    return forms.MultipleChoiceField(
        label=capfirst(slice_),
        required=False,
        widget=ChipsWidget,
    )


class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ("configuration", "stack", "seed")

    class Media:
        js = ("portal/js/batch_form.js",)

    # the identity's bench, which the admin gives each form of a request
    bench: Bench

    configuration = forms.ChoiceField(
        label=_("Use"),
        widget=UnfoldAdminSelect2Widget(
            attrs={"data-placeholder": _("Pick a configuration")}
        ),
    )
    stack = forms.ChoiceField(
        label=_("On"),
        widget=UnfoldAdminSelect2Widget(attrs={"data-placeholder": _("Pick a stack")}),
    )
    case_tags = forms.MultipleChoiceField(
        label=_("Case tags"),
        widget=HeardSelect2MultipleWidget(
            attrs={"data-placeholder": _("Pick case tags")}
        ),
    )
    seed = forms.IntegerField(
        label=_("Seed"),
        required=False,
        min_value=0,
        max_value=MAX_SEED,
        widget=UnfoldAdminIntegerFieldWidget(
            attrs={"placeholder": _("none: runs go unseeded")}
        ),
    )
    instruction = variations_field("instruction")
    output = variations_field("output")
    coercion = variations_field("coercion")
    reasoning = variations_field("reasoning")
    sampling = variations_field("sampling")
    toolset = variations_field("toolset")

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.plan: Plan | None = None

        # a batch kept is shown, never changed
        if self.instance.pk:
            return

        bench = self.bench
        visible = {
            entity: bench.visible(entity) for entity in ("configuration", *SLICES)
        }
        own = _own(visible)

        self._choose("configuration", _names(visible["configuration"]))
        self._choose("stack", bench.names("stack"))
        self._choose("case_tags", bench.tags("case"), blank=False)

        for entity in SLICES:
            optional = [NONE] if entity in OPTIONAL else []
            self._choose(entity, _names(visible[entity]) + optional, blank=False)

        # what each configuration has of each slice, which the form ticks as
        # the configuration is put in (js/batch_form.js)
        self.fields["configuration"].widget.attrs["data-variations"] = json.dumps(own)

        if not self.is_bound:
            chosen = own.get(self.initial.get("configuration", ""), {})

            for entity, name in chosen.items():
                _ = self.initial.setdefault(entity, [name])

            _ = self.initial.setdefault("seed", drawn_seed())

    def _choose(self, name: str, choices: list[str], blank: bool = True) -> None:
        field = self.fields[name]
        assert isinstance(field, forms.ChoiceField)
        field.choices = [("", "")] * blank + [(choice, choice) for choice in choices]

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()

        if self.errors:
            return cleaned

        bench = self.bench
        ticked: dict[EntityName, list[str]] = {
            entity: cleaned.get(entity) or [] for entity in SLICES
        }
        cells = prod(len(names) or 1 for names in ticked.values())

        if cells > MOST_CELLS:
            raise ValidationError(
                _(
                    "The variations ticked cross into %(cells)d cells, and a batch "
                    + "holds %(most)d at most."
                ),
                params={"cells": cells, "most": MOST_CELLS},
            )

        cell = bench.cell_of(cleaned["configuration"], cleaned["stack"])
        variations = {
            entity: [
                None if name == NONE else bench.variation_named(entity, name)
                for name in names
            ]
            for entity, names in ticked.items()
        }
        self.plan = Plan.of(
            bench, crossed(cell, variations), cleaned["case_tags"], cleaned["seed"]
        )

        return cleaned

    def save(self, commit: bool = True) -> Any:
        """The batch, as asked and as its plan stands."""
        plan = self.plan
        assert plan is not None

        batch = self.instance
        cleaned = self.cleaned_data
        batch.owner = IdentityModel.objects.get(name=self.bench.identity)
        batch.tags = list(cleaned["case_tags"])
        batch.variations = {
            entity: list(cleaned[entity]) for entity in SLICES if cleaned.get(entity)
        }
        batch.cells = batches.cells_of(plan)
        batch.held_back = batches.held_back_of(plan)
        batch.cases = batches.cases_of(plan)

        return super().save(commit)


def _names(models: list[BranchModel]) -> list[str]:
    return sorted({model.name for model in models})


def _own(visible: dict[str, list[BranchModel]]) -> dict[str, dict[str, str]]:
    """Each configuration's variation of each slice, as the identity names it."""
    named: dict[str, dict[int, str]] = {}

    for entity in SLICES:
        names: dict[int, str] = {}

        for model in visible[entity]:
            _ = names.setdefault(model.trail_id, model.name)

        named[entity] = names

    own: dict[str, dict[str, str]] = {}

    for model in visible["configuration"]:
        variations: dict[str, str] = {}

        for entity in SLICES:
            trail = getattr(model.trail, f"{entity}_id")

            if trail is None:
                variations[entity] = NONE
            elif trail in named[entity]:
                variations[entity] = named[entity][trail]

        own[model.name] = variations

    return own
