# pyright: basic
from functools import cached_property

import tomli_w
from django.db.models import PROTECT, CharField, ForeignKey, JSONField, URLField

from chatddx.core.choices import ProviderChoices
from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ConnectionTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_connection"

    provider = CharField(max_length=255, choices=ProviderChoices.choices)
    model = CharField(max_length=255)
    endpoint = URLField(max_length=2048)
    profile: JSONField = JSONField(
        default=dict,
        blank=True,
    )


class ConnectionBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_connection_branch"

    target = ForeignKey(
        ConnectionTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Connection(BranchProxy, ConnectionBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Connection"
        verbose_name_plural = "Connections"

    @cached_property
    def profile_toml(self) -> str:
        return tomli_w.dumps(self.target.profile)  # pyright: ignore[reportAttributeAccessIssue]
