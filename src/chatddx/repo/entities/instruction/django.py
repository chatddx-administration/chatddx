# pyright: basic

from django.db.models import PROTECT, ForeignKey, JSONField, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class InstructionTrailModel(TrailModel):
    class Meta(TrailModel.Meta):
        app_label = "orm"
        db_table = "agents_instruction"

    system = TextField(blank=True)
    user = TextField()
    # a list, whose order jsonb keeps
    variables = JSONField(default=list)


class InstructionBranchModel(BranchModel):
    class Meta(BranchModel.Meta):
        app_label = "orm"
        db_table = "agents_instruction_branch"

    target = ForeignKey(
        InstructionTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )


class Instruction(BranchProxy, InstructionBranchModel):
    class Meta:
        proxy = True
        app_label = "orm"
        verbose_name = "Instruction"
        verbose_name_plural = "Instructions"
