# pyright: basic
from typing import final, override

from django.contrib import admin

from chatddx.experiment.models import ExperimentModel


class Experiment(ExperimentModel):
    """Read-only admin-facing proxy for ExperimentModel.

    Like Session (chatddx.history.proxies.Session), an Experiment is never
    hand-authored or edited in place -- it's only ever generated (today by
    chatddx.repo.shufflers.experiment, eventually by saving a Batch) -- so
    the admin registered against this proxy (see
    chatddx.django.portal.admin.experiment) exposes it purely for
    inspection, with no add/change/delete affordances.
    """

    @final
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Experiment"
        verbose_name_plural = "Experiments"

    @override
    def __str__(self):
        return f"[{self.uuid}]"

    @admin.display(description="Tags")
    def tags_display(self):
        return ", ".join(self.tag_list) or None

    @admin.display(description="Collaborators")
    def collaborators_csv(self):
        return ", ".join(str(c) for c in self.collaborators.all()) or None


class SharedExperiment(Experiment):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Experiment"
        verbose_name_plural = "Shared Experiments"
