# pyright: basic
from __future__ import annotations

import uuid
from typing import Any

from django.contrib.postgres.fields import ArrayField
from django.db.models import (
    CASCADE,
    BigIntegerField,
    CharField,
    DateTimeField,
    ForeignKey,
    JSONField,
    Model,
    UUIDField,
)

from chatddx.core.models import IdentityModel
from chatddx.history.models import RunModel
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.sampling.django import SamplingBranchModel
from chatddx.repo.entities.stack.django import StackBranchModel


class BatchModel(Model):
    class Meta:
        app_label = "portal"
        db_table = "portal_batch"
        ordering = ("-timestamp", "-pk")

    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    timestamp = DateTimeField(auto_now_add=True)
    owner = ForeignKey(
        IdentityModel,
        on_delete=CASCADE,
        db_constraint=False,
        related_name="+",
    )
    owner_id: int

    configuration = CharField(max_length=255)
    stack = CharField(max_length=255)
    tags = ArrayField(CharField(max_length=255))
    variations: JSONField[dict[str, list[str]]] = JSONField(default=dict)
    seed = BigIntegerField(
        default=None,
        null=True,
        blank=True,
    )

    cells: JSONField[list[dict[str, Any]]] = JSONField(default=list)
    held_back: JSONField[list[dict[str, Any]]] = JSONField(default=list)
    cases: JSONField[list[dict[str, Any]]] = JSONField(default=list)

    def __str__(self) -> str:
        return str(self.uuid)[:8]

    @property
    def trials(self) -> int:
        return len(self.cells) * len(self.cases)


class Batch(BatchModel):
    class Meta:
        app_label = "portal"
        proxy = True


class Case(CaseBranchModel):
    class Meta:
        app_label = "portal"
        proxy = True

    def __str__(self) -> str:
        return self.name


class Configuration(ConfigurationBranchModel):
    class Meta:
        app_label = "portal"
        proxy = True

    def __str__(self) -> str:
        return self.name


class Sampling(SamplingBranchModel):
    class Meta:
        app_label = "portal"
        proxy = True

    def __str__(self) -> str:
        return self.name


class Stack(StackBranchModel):
    class Meta:
        app_label = "portal"
        proxy = True

    def __str__(self) -> str:
        return self.name


class Run(RunModel):
    class Meta:
        app_label = "portal"
        proxy = True

    def __str__(self) -> str:
        return str(self.uuid)[:8]
