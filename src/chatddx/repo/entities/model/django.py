# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ModelTrailModel(TrailModel):
    blob = TextField()


class ModelBranchModel(BranchModel):
    target = ForeignKey(
        ModelTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


# not `Model`, which every module that star-imports the models would take
# for Django's
class LanguageModel(BranchProxy, ModelBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Model"
        verbose_name_plural = "Models"
