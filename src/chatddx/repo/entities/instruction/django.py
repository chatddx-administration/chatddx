# pyright: basic

from django.db.models import PROTECT, ForeignKey, JSONField, TextField

from chatddx.repo.families.django import BranchModel, BranchProxy, TrailModel


class InstructionTrailModel(TrailModel):
    system = TextField(blank=True)
    user = TextField()
    # a list, whose order jsonb keeps
    variables = JSONField(default=list)

    class Meta(TrailModel.Meta):
        db_table = "repo_instruction_trail"


class InstructionBranchModel(BranchModel):
    trail = ForeignKey(
        InstructionTrailModel,
        on_delete=PROTECT,
        related_name="branches",
    )

    class Meta(BranchModel.Meta):
        db_table = "repo_instruction_branch"


class Instruction(BranchProxy, InstructionBranchModel):
    class Meta(BranchProxy.Meta):
        proxy = True
        verbose_name = "Instruction"
        verbose_name_plural = "Instructions"
