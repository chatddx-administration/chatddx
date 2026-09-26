# pyright: basic
"""
A batch, as the portal keeps it for whoever asked for it: what was asked,
and the plan they confirmed. Nothing outside the portal refers to it; a run
never points at a batch (backlog/post-endgame.md). And a case, the repo's,
as the portal's pages are of it.
"""

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
from chatddx.repo.entities.case.django import CaseBranchModel


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
    # held without a constraint, so that nothing the rest of chatddx deletes
    # waits on a table it doesn't know of: the portal's batches go with
    # their owner, and a batch whose owner went elsewhere is no one's
    owner = ForeignKey(
        IdentityModel,
        on_delete=CASCADE,
        db_constraint=False,
        related_name="+",
    )
    owner_id: int

    # what was asked: the configuration and the stack as the owner named
    # them, the case tags, the variations ticked by slice, and the seed
    configuration = CharField(max_length=255)
    stack = CharField(max_length=255)
    tags = ArrayField(CharField(max_length=255))
    variations: JSONField[dict[str, list[str]]] = JSONField(default=dict)
    seed = BigIntegerField(
        default=None,
        null=True,
        blank=True,
    )

    # the plan confirmed: each cell to run, with what it sets, the
    # fingerprint of the configuration it comes to and the seed its trials
    # take; each cell held back and why; and the cases, by name and trail
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
    """A version of a case: the portal's pages are of the owner's timelines."""

    class Meta:
        app_label = "portal"
        proxy = True

    def __str__(self) -> str:
        return self.name
