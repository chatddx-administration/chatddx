# pyright: basic
from functools import cached_property
from typing import final, override

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from chatddx.experiment.models import ExperimentModel, RunModel
from chatddx.history.proxies import Session
from chatddx.utils import render_json_html


class Experiment(ExperimentModel):
    @final
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Experiment"
        verbose_name_plural = "Experiments"

    @override
    def __str__(self):
        timestamp = self.timestamp.strftime("%Y-%m-%d %H:%M")
        tags = self.tags_display() or "no tags"
        return f"{timestamp} — {tags}"

    @admin.display(description="Tags")
    def tags_display(self):
        return ", ".join(self.tag_list) or None

    @admin.display(description="Collaborators")
    def collaborators_csv(self):
        return ", ".join(str(c) for c in self.collaborators.all()) or None

    @cached_property
    def agent_link(self):
        if self.agent_branch_id:  # pyright: ignore[reportAttributeAccessIssue]
            url = reverse(
                "admin:orm_superagent_change",
                args=[self.agent_branch_id],  # pyright: ignore[reportAttributeAccessIssue]
            )
            label = f"{self.agent_branch_name} ({self.agent.fingerprint[:6]})"  # pyright: ignore[reportAttributeAccessIssue]
        else:
            url = (
                reverse("admin:orm_superagent_add")
                + f"?agent_fingerprint={self.agent.fingerprint}"
            )
            label = self.agent.fingerprint[:6]

        return format_html('<a href="{}">{}</a>', url, label)

    @cached_property
    def case_link(self):
        if self.case_branch_id:  # pyright: ignore[reportAttributeAccessIssue]
            url = reverse(
                "admin:orm_case_change",
                args=[self.case_branch_id],  # pyright: ignore[reportAttributeAccessIssue]
            )
            label = f"{self.case_branch_name} ({self.case.fingerprint[:6]})"  # pyright: ignore[reportAttributeAccessIssue]
        else:
            url = (
                reverse("admin:orm_case_add")
                + f"?case_fingerprint={self.case.fingerprint}"
            )
            label = self.case.fingerprint[:6]

        return format_html('<a href="{}">{}</a>', url, label)

    @cached_property
    def expect_link(self):
        short_hash = self.expect.fingerprint[:6]
        expect_branch_name = self.expect_branch_name  # pyright: ignore[reportAttributeAccessIssue]
        label = (
            f"{expect_branch_name} ({short_hash})" if expect_branch_name else short_hash
        )

        expect_case_branch_id = self.expect_case_branch_id  # pyright: ignore[reportAttributeAccessIssue]
        if not expect_case_branch_id:
            return label

        url = reverse("admin:orm_case_change", args=[expect_case_branch_id])
        return format_html('<a href="{}">{}</a>', url, label)


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

    @cached_property
    def session_link(self):
        if not self.session_id:
            return None

        url = reverse("admin:orm_session_change", args=[self.session_id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            Session.objects.get(pk=self.session_id),
        )

    @cached_property
    def result_html(self):
        return render_json_html(self.result)


class SharedRun(Run):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Shared Run"
        verbose_name_plural = "Shared Runs"
