# src/chatddx/repo/shufflers/wipe.py

from __future__ import annotations

from django.db import transaction

from chatddx.core.models import IdentityModel, TagModel
from chatddx.experiment.models import ExperimentModel, RunModel
from chatddx.history.models import MessageModel, SessionModel
from chatddx.repo.branch_models import (
    AgentBranchModel,
    CaseBranchModel,
    ConnectionBranchModel,
    ExpectBranchModel,
    OutputTypeBranchModel,
    SamplingParamsBranchModel,
    ScorerBranchModel,
    ToolBranchModel,
    ToolGroupBranchModel,
)
from chatddx.utils import make_async

# All ownable branches
BRANCH_MODELS = [
    AgentBranchModel,
    ConnectionBranchModel,
    SamplingParamsBranchModel,
    OutputTypeBranchModel,
    ToolGroupBranchModel,
    ToolBranchModel,
    CaseBranchModel,
    ExpectBranchModel,
    ScorerBranchModel,
]


def wipe_data(owner_name: str) -> bool:
    try:
        owner = IdentityModel.objects.get(name=owner_name)
    except IdentityModel.DoesNotExist:
        return False

    with transaction.atomic():
        # Deletion order follows the PROTECT chain: Message protects
        # Session, Run protects both Session and Experiment.
        MessageModel.objects.filter(session__owner=owner).delete()
        RunModel.objects.filter(owner=owner).delete()
        SessionModel.objects.filter(owner=owner).delete()
        ExperimentModel.objects.filter(owner=owner).delete()

        for branch_model in BRANCH_MODELS:
            branch_model.objects.filter(owner=owner).delete()

        TagModel.objects.filter(owner=owner).delete()

        owner.delete()

    return True


wipe_data_async = make_async(wipe_data)
