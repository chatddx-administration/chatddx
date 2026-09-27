# pyright: basic
import json
from dataclasses import dataclass
from math import prod
from typing import Any, ClassVar

from django import forms
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from pydantic import ValidationError as PydanticValidationError
from unfold.widgets import (
    UnfoldAdminDecimalFieldWidget,
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
from chatddx.django.portal import batches, cases, variations
from chatddx.django.portal.models import Batch
from chatddx.django.portal.slices import DEFAULTS
from chatddx.repo.entities.case.pydantic import (
    EXPECTS_NONE,
    TARGET_KINDS,
    CaseBranchDetails,
    CaseTrailIn,
    Expected,
    Target,
    TargetKind,
)
from chatddx.repo.entities.sampling.pydantic import SamplingTrailIn
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.families.pydantic import BranchDetails
from chatddx.scoring.scorers.patterns import unread_pattern

MOST_CELLS = 100


class HeardSelect2MultipleWidget(UnfoldAdminSelect2MultipleWidget):
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


CASES_FORM = "batch-cases"


class CasesForm(forms.Form):
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
    def to_python(self, value: Any) -> list[str]:
        tags = (str(tag).strip() for tag in super().to_python(value) or [])
        return list(dict.fromkeys(tag for tag in tags if tag))

    def valid_value(self, value: Any) -> bool:
        return not any(character.isspace() for character in str(value))


@dataclass(frozen=True)
class TargetRow:
    kind: TargetKind
    label: Any
    none: forms.BoundField | None
    text: forms.BoundField
    pattern: forms.BoundField


class CaseForm(forms.Form):
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
        self.targets: dict[TargetKind, Target] = {}

        for kind in TARGET_KINDS:
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


SAMPLING_SET = (
    "temperature",
    "top_p",
    "top_k",
    "max_tokens",
    "presence_penalty",
    "frequency_penalty",
)


class SamplingForm(forms.Form):
    BLANK: ClassVar[dict[str, Any]] = {"defaults": "recommended"}

    edited = forms.CharField(required=False, widget=forms.HiddenInput)
    head = forms.IntegerField(required=False, widget=forms.HiddenInput)
    since = forms.IntegerField(required=False, widget=forms.HiddenInput)

    name = forms.CharField(
        label=_("Name"), max_length=255, widget=UnfoldAdminTextInputWidget
    )
    defaults = forms.ChoiceField(
        label=_("A setting left out"),
        choices=lambda: [(name, f"{name}: {said}") for name, said in DEFAULTS.items()],
        widget=UnfoldAdminSelectWidget,
    )
    temperature = forms.FloatField(
        label=_("Temperature"),
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(attrs={"step": "0.05"}),
    )
    top_p = forms.FloatField(
        label=_("Top p"),
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(attrs={"step": "0.05"}),
    )
    top_k = forms.IntegerField(
        label=_("Top k"), required=False, widget=UnfoldAdminIntegerFieldWidget
    )
    max_tokens = forms.IntegerField(
        label=_("Max tokens"), required=False, widget=UnfoldAdminIntegerFieldWidget
    )
    presence_penalty = forms.FloatField(
        label=_("Presence penalty"),
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(attrs={"step": "0.1"}),
    )
    frequency_penalty = forms.FloatField(
        label=_("Frequency penalty"),
        required=False,
        widget=UnfoldAdminDecimalFieldWidget(attrs={"step": "0.1"}),
    )
    stop = forms.CharField(
        label=_("Stop"),
        help_text=_("One a line, or a JSON list, where one holds a line's end."),
        required=False,
        strip=False,
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 2}),
    )

    def __init__(self, owner: str, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.owner: str = owner
        self.made: SamplingTrailIn | None = None

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        why = variations.refused(name)

        if why is not None:
            raise ValidationError(why)

        return name

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        asked = {
            "defaults": cleaned.get("defaults"),
            **{name: cleaned.get(name) for name in SAMPLING_SET},
            "stop": _stops(cleaned.get("stop") or ""),
        }

        if any(name in self.errors for name in asked):
            return cleaned

        try:
            self.made = SamplingTrailIn.model_validate(asked)
        except PydanticValidationError as e:
            for error in e.errors(include_url=False, include_input=False):
                where = str(error["loc"][0]) if error["loc"] else None
                self.add_error(where if where in self.fields else None, error["msg"])

        return cleaned

    @property
    def trail(self) -> SamplingTrailIn:
        assert self.made is not None
        return self.made

    @property
    def details(self) -> BranchDetails:
        return BranchDetails(name=self.cleaned_data["name"], owner=self.owner)

    @staticmethod
    def initial_of(trail: Any) -> dict[str, Any]:
        return {
            "defaults": trail.defaults,
            **{name: getattr(trail, name) for name in SAMPLING_SET},
            "stop": _stops_written(trail.stop),
        }


def _stops(text: str) -> list[str] | None:
    if text.lstrip().startswith("["):
        try:
            listed = json.loads(text)
        except json.JSONDecodeError:
            listed = None

        if isinstance(listed, list) and all(isinstance(each, str) for each in listed):
            return listed

    return [line for line in text.splitlines() if line.strip()] or None


def _stops_written(stop: list[str] | None) -> str:
    if stop is None:
        return ""

    if (
        not stop
        or stop[0].lstrip().startswith("[")
        or any("\n" in each or "\r" in each or not each.strip() for each in stop)
    ):
        return json.dumps(stop, ensure_ascii=False)

    return "\n".join(stop)
