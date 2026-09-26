# pyright: basic
"""
The portal's forms. The Batch form: the repl's cell and batch, with its
slices varied. Use and On put a configuration and a stack in the cell, the
case tags say which cases it runs on, the variations ticked on each slice
are crossed into the batch's cells, and the seed is each trial's, a greedy
cell's aside. The case form: a case as its page saves it, a new version of
whichever case its name names.
"""

import json
from dataclasses import dataclass
from math import prod
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from unfold.widgets import (
    UnfoldAdminIntegerFieldWidget,
    UnfoldAdminSelect2MultipleWidget,
    UnfoldAdminSelect2Widget,
    UnfoldAdminSelectWidget,
    UnfoldAdminTextareaWidget,
    UnfoldAdminTextInputWidget,
    UnfoldBooleanWidget,
)

from chatddx.bench.bench import MAX_SEED, Bench, drawn_seed
from chatddx.bench.cell import NONE, OPTIONAL, SLICES
from chatddx.bench.plan import Plan, crossed
from chatddx.core.models import IdentityModel
from chatddx.django.portal import batches, cases
from chatddx.django.portal.models import Batch
from chatddx.repo.entities.case.pydantic import (
    EXPECTS_NONE,
    TARGET_KINDS,
    CaseBranchDetails,
    CaseTrailIn,
    Expected,
    Target,
    TargetKind,
)
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.scoring.scorers.patterns import unread_pattern

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
        batch.cases = batches.cases_of(plan.cases)

        return super().save(commit)


# the form a batch's page adds cases with, apart from the page's own
CASES_FORM = "batch-cases"


class CasesForm(forms.Form):
    """The cases to add to a kept batch: those with any of the tags, and those named."""

    case_tags = forms.MultipleChoiceField(
        label=_("With the case tags"),
        required=False,
        widget=UnfoldAdminSelect2MultipleWidget(
            attrs={"data-placeholder": _("Pick case tags"), "form": CASES_FORM}
        ),
    )
    cases = forms.MultipleChoiceField(
        label=_("Or the cases"),
        required=False,
        widget=UnfoldAdminSelect2MultipleWidget(
            attrs={"data-placeholder": _("Pick cases"), "form": CASES_FORM}
        ),
    )

    def __init__(self, bench: Bench, batch: Batch, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.bench: Bench = bench
        self.batch: Batch = batch
        # the cases found once the form is valid
        self.unheld: list[BranchModel] = []

        for name, choices in (
            ("case_tags", bench.tags("case")),
            ("cases", _names(bench.visible("case"))),
        ):
            field = self.fields[name]
            assert isinstance(field, forms.ChoiceField)
            field.choices = [(choice, choice) for choice in choices]

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()

        if self.errors:
            return cleaned

        tags, names = cleaned.get("case_tags") or [], cleaned.get("cases") or []

        if not (tags or names):
            raise ValidationError(_("Pick case tags or cases to add."))

        self.unheld = batches.unheld(self.bench, self.batch, tags, names)

        if not self.unheld:
            raise ValidationError(_("The batch holds every case picked already."))

        return cleaned


class TagsField(forms.MultipleChoiceField):
    """Tags: those the owner's cases have, or new ones, each a word."""

    def to_python(self, value: Any) -> list[str]:
        tags = (str(tag).strip() for tag in super().to_python(value) or [])
        return list(dict.fromkeys(tag for tag in tags if tag))

    def valid_value(self, value: Any) -> bool:
        return not any(character.isspace() for character in str(value))


@dataclass(frozen=True)
class TargetRow:
    """A kind of target's fields, as the page lays them out."""

    kind: TargetKind
    label: Any
    none: forms.BoundField | None
    text: forms.BoundField
    pattern: forms.BoundField


class CaseForm(forms.Form):
    """
    A case as its page saves it: the name it is saved under, its language,
    vignette and targets, and its tags. What the page began from rides
    along: the case it is of, the head it found, and the version it began
    from, where it is an earlier one.
    """

    class Media:
        js = ("portal/js/case_form.js",)

    edited = forms.CharField(required=False, widget=forms.HiddenInput)
    head = forms.IntegerField(required=False, widget=forms.HiddenInput)
    since = forms.IntegerField(required=False, widget=forms.HiddenInput)

    name = forms.CharField(
        label=_("Name"), max_length=255, widget=UnfoldAdminTextInputWidget
    )
    language = forms.ChoiceField(
        label=_("Language"),
        required=False,
        choices=[("", "—"), ("en", _("English")), ("sv", _("Swedish"))],
        widget=UnfoldAdminSelectWidget,
    )
    vignette = forms.CharField(
        label=_("Vignette"),
        strip=False,
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 12}),
    )
    tags = TagsField(
        label=_("Tags"),
        required=False,
        widget=UnfoldAdminSelect2MultipleWidget(
            attrs={
                "data-tags": "true",
                "data-token-separators": '[" ", ","]',
                "data-placeholder": _("Tag the case"),
            }
        ),
    )

    def __init__(self, owner: str, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.owner: str = owner
        # what the form comes to once it is valid
        self.targets: dict[TargetKind, Target] = {}

        for kind in TARGET_KINDS:
            # none expected, the text and the pattern are off, and not sent
            off = {":disabled": "none"} if kind in EXPECTS_NONE else {}

            if kind in EXPECTS_NONE:
                self.fields[f"{kind}_none"] = forms.BooleanField(
                    label=_("None expected"),
                    required=False,
                    widget=UnfoldBooleanWidget(attrs={"x-model": "none"}),
                )

            self.fields[f"{kind}_text"] = forms.CharField(
                label=_("Text"),
                required=False,
                widget=UnfoldAdminTextareaWidget(attrs={"rows": 2, **off}),
            )
            self.fields[f"{kind}_pattern"] = forms.CharField(
                label=_("Pattern"),
                required=False,
                widget=UnfoldAdminTextInputWidget(attrs=off),
            )

        # the tags the owner's cases have, and those the page holds already
        held: list[str] = (
            self.data.getlist("tags")
            if isinstance(self.data, QueryDict)
            else self.initial.get("tags") or []
        )
        tags = dict.fromkeys([*Bench(owner, own=("case",)).tags("case"), *held])
        field = self.fields["tags"]
        assert isinstance(field, forms.ChoiceField)
        field.choices = [(str(tag), str(tag)) for tag in tags]

    @property
    def rows(self) -> list[TargetRow]:
        return [
            TargetRow(
                kind,
                cases.KINDS[kind],
                self[f"{kind}_none"] if kind in EXPECTS_NONE else None,
                self[f"{kind}_text"],
                self[f"{kind}_pattern"],
            )
            for kind in TARGET_KINDS
        ]

    def clean_name(self) -> str:
        name = self.cleaned_data["name"]

        if "/" in name:
            raise ValidationError(
                _("A name can't hold '/': the repl parts an owner from a name by it.")
            )

        return name

    def clean_vignette(self) -> str:
        vignette = cases.vignette_of(self.owner, self.cleaned_data["vignette"])

        if not vignette:
            raise ValidationError(_("A case is its vignette: write it."))

        return vignette

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()

        for kind in TARGET_KINDS:
            text = cleaned.get(f"{kind}_text") or None
            pattern = cleaned.get(f"{kind}_pattern") or None

            if pattern and (why := unread_pattern(pattern)):
                self.add_error(
                    f"{kind}_pattern", _("Doesn't parse: %(why)s") % {"why": why}
                )
            elif cleaned.get(f"{kind}_none"):
                if text or pattern:
                    self.add_error(
                        f"{kind}_none",
                        _("None expected takes no text or pattern: clear them."),
                    )
                else:
                    self.targets[kind] = False
            elif text or pattern:
                self.targets[kind] = Expected(text=text, pattern=pattern)

        return cleaned

    @property
    def trail(self) -> CaseTrailIn:
        return CaseTrailIn(vignette=self.cleaned_data["vignette"])

    @property
    def draft(self) -> cases.Draft:
        """The case as it would be saved, beside the one it would replace."""
        cleaned = self.cleaned_data

        return cases.Draft(
            cleaned["vignette"],
            cleaned["language"] or None,
            [cases.shown_of(kind, self.targets.get(kind)) for kind in TARGET_KINDS],
            sorted(cleaned["tags"]),
        )

    @property
    def details(self) -> CaseBranchDetails:
        cleaned = self.cleaned_data

        return CaseBranchDetails.model_validate(
            {
                "name": cleaned["name"],
                "owner": self.owner,
                "language": cleaned["language"] or None,
                "targets": self.targets,
                "tags": cleaned["tags"],
            }
        )


def initial_of(version: cases.Version, timeline: cases.Timeline) -> dict[str, Any]:
    """The case form, as a version fills it: the head's, or an earlier one's."""
    initial: dict[str, Any] = {
        "edited": timeline.name,
        "head": timeline.head.row.pk,
        "since": None if version.is_head else version.number,
        "name": timeline.name,
        "language": version.language or "",
        "vignette": version.vignette,
        "tags": version.tags,
    }

    for target in version.targets:
        initial[f"{target.kind}_none"] = target.none
        initial[f"{target.kind}_text"] = target.text or ""
        initial[f"{target.kind}_pattern"] = target.pattern or ""

    return initial


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
