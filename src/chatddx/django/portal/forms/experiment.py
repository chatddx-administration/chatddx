# pyright: basic
from typing import Any

from django import forms
from unfold.widgets import UnfoldAdminSelectWidget

from chatddx.core.choices import RunStatusChoices
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


class ExperimentForm(forms.ModelForm):
    class Meta:
        model = Experiment
        fields = ("agent", "case", "expect", "collaborators")

    initial_run_status = forms.ChoiceField(
        choices=INITIAL_RUN_STATUS_CHOICES,
        initial=RunStatusChoices.QUEUED.value,
        widget=UnfoldAdminSelectWidget,
        label="Initial run status",
    )

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        # The experiment is immutable once it exists, so the field only ever
        # applies to the run made alongside a brand new one.
        if self.instance.pk:
            del self.fields["initial_run_status"]
