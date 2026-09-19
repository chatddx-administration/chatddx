# pyright: basic
import json
from typing import Any

from django import forms
from unfold.widgets import UnfoldAdminSelectWidget

from chatddx.core.choices import RunStatusChoices
from chatddx.django.orm.qs import expects_by_case
from chatddx.history.proxies import Experiment

# Sentinel for "create the experiment, but no run to go with it". It lives
# next to the run statuses in the same field, so it must not collide with one.
NO_RUN = "no_run"
assert NO_RUN not in RunStatusChoices.values

INITIAL_RUN_STATUS_CHOICES = (
    (RunStatusChoices.QUEUED.value, RunStatusChoices.QUEUED.label),
    (RunStatusChoices.STORED.value, RunStatusChoices.STORED.label),
    (NO_RUN, "Don't run"),
)

# What the `expect` field reads as while there is no case to draw
# expectations from.
NO_CASE_LABEL = "Select a case first"

MISMATCHED_EXPECT = "That expectation doesn't belong to the chosen case."


class ExperimentForm(forms.ModelForm):
    class Meta:
        model = Experiment
        fields = ("agent", "case", "expect", "collaborators")

    class Media:
        js = ("js/experiment_expect_selector.js",)

    initial_run_status = forms.ChoiceField(
        choices=INITIAL_RUN_STATUS_CHOICES,
        initial=RunStatusChoices.QUEUED.value,
        widget=UnfoldAdminSelectWidget,
        label="Initial run status",
    )

    def __init__(self, *args: Any, **kwargs: Any):
        self.request = kwargs.pop("request")
        self._expects_by_case: dict[int, list[int]] | None = None

        super().__init__(*args, **kwargs)

        # The experiment is immutable once it exists, so the field only ever
        # applies to the run made alongside a brand new one. The change form
        # is read-only throughout, so there is nothing else to set up either.
        if self.instance.pk:
            del self.fields["initial_run_status"]
            return

        self._pair_expect_with_case()

    def clean(self):
        cleaned_data = super().clean()

        case = cleaned_data.get("case")
        expect = cleaned_data.get("expect")

        if case is None or expect is None:
            return cleaned_data

        if expect.pk not in self.expects_by_case().get(case.pk, ()):
            self.add_error("expect", MISMATCHED_EXPECT)

        return cleaned_data

    def expects_by_case(self) -> dict[int, list[int]]:
        if self._expects_by_case is None:
            self._expects_by_case = expects_by_case(self.request.user.username)

        return self._expects_by_case

    def _pair_expect_with_case(self):
        """
        An expectation belongs to a case (see `CaseBranchModel.expects`), so
        the `expect` field is worth nothing until a case is chosen, and then
        only for that case's own.

        The attributes set here are what `js/experiment_expect_selector.js`
        narrows the field by as the case changes; `clean()` is what makes the
        pairing hold for a post that never met the script.
        """
        # The admin wraps a relation's widget for its add/change links, and
        # it is the select underneath that has to carry the attributes.
        widget = self.fields["expect"].widget
        widget = getattr(widget, "widget", widget)

        widget.attrs["data-expects-by-case"] = json.dumps(
            self.expects_by_case(),
            separators=(",", ":"),
        )
        widget.attrs["data-no-case-label"] = NO_CASE_LABEL

        if not self._chosen_case():
            widget.attrs["disabled"] = True

    def _chosen_case(self) -> str:
        """
        The case the form is rendering with, straight off the raw data: on a
        post that comes back with errors it is what was submitted, otherwise
        whatever initial data (an `?case=` on the add link, say) asked for.
        """
        if self.is_bound:
            return str(self.data.get(self.add_prefix("case")) or "")

        return str(self.initial.get("case") or "")
