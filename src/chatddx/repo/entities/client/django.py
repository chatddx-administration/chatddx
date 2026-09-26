# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ClientTrailModel(TrailModel):
    build = TextField(null=True, blank=True)

    class Meta(TrailModel.Meta):
        db_table = "repo_client_trail"


class ClientBranchModel(BranchModel):
    trail = ForeignKey(
        ClientTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_client_branch"


class Client(BranchProxy, ClientBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Client"
        verbose_name_plural = "Clients"
