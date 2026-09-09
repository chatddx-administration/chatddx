# pyright: basic
from typing import final, override

from django.contrib import admin

from chatddx.experiment.models import ExperimentModel, RunModel


class Experiment(ExperimentModel):
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


class Run(RunModel):
    @final
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Run"
        verbose_name_plural = "Runs"

    @override
    def __str__(self):
        return f"[{self.uuid}]"

    @admin.display(description="Collaborators")
    def collaborators_csv(self):
        return ", ".join(str(c) for c in self.collaborators.all()) or None


class SharedRun(Run):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Run"
        verbose_name_plural = "Shared Runs"
