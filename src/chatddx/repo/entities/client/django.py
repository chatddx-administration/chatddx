# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ClientTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_client"

    build = TextField(null=True, blank=True)


class ClientBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_client_branch"

    target = ForeignKey(
        ClientTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Client(BranchProxy, ClientBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Client"
        verbose_name_plural = "Clients"
