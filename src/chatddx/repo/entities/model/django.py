# pyright: basic

from django.db.models import PROTECT, ForeignKey, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class ModelTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_model"

    blob = TextField()


class ModelBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_model_branch"

    target = ForeignKey(
        ModelTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


# not `Model`, which every module that star-imports the models would take
# for Django's
class LanguageModel(BranchProxy, ModelBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Model"
        verbose_name_plural = "Models"
