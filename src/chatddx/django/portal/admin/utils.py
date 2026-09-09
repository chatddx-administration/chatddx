from django.db.models import OuterRef, QuerySet, Subquery
from django.urls import reverse
from django.utils.html import format_html

from chatddx.experiment.proxies import Experiment
from chatddx.history.proxies import Message
from chatddx.repo.base import BranchModel
from chatddx.repo.branch_models import ExpectBranchModel
from chatddx.repo.proxies import Agent, Case


def get_branch_link(obj: BranchModel, field_name: str):
    branch_id = getattr(obj, f"{field_name}_id")
    branch_name = getattr(obj, f"{field_name}_name")
    target = getattr(obj.target, field_name)
    label = branch_name or target.fingerprint[:6]
    if branch_id:
        url = (
            reverse(
                f"admin:orm_{field_name.replace('_', '')}_change",
                args=[branch_id],
            )
            + f"?from_agent={obj.pk}"
        )
    else:
        url = (
            reverse(
                f"admin:orm_{field_name.replace('_', '')}_add",
            )
            + f"?from_agent={obj.pk}&target={target.id}"
        )

    return format_html('<a href="{}">{}</a>', url, label)


def qs_messages(qs: QuerySet[Message], owner_name: str):
    agent_branch = Agent.objects.filter(
        target=OuterRef("agent"),
        owner__name=owner_name,
    ).order_by("-timestamp")

    qs = qs.annotate(
        agent_branch_id=Subquery(agent_branch.values("id")[:1]),
        agent_branch_name=Subquery(agent_branch.values("name")[:1]),
    )

    return qs.order_by("timestamp")


def qs_experiments(qs: QuerySet[Experiment], owner_name: str):
    """Annotate `qs` with the branch id/name for each of an Experiment's
    pinned targets (agent, case, expect), scoped to `owner_name` -- see
    Experiment.agent_link/case_link/expect_link (chatddx/experiment/proxies.py)
    for how these are turned into links.

    An Expect has no admin page of its own (it's only ever edited inline on
    its Case -- see ExpectInline), so `expect_case_branch_id` locates the
    Case branch that owns it instead of an Expect branch.
    """

    def branch_subquery(
        model: type[Agent | Case | ExpectBranchModel], target_field: str
    ):
        return model.objects.filter(
            target=OuterRef(target_field),
            owner__name=owner_name,
        ).order_by("-timestamp")

    agent_branch = branch_subquery(Agent, "agent")
    case_branch = branch_subquery(Case, "case")
    expect_branch = branch_subquery(ExpectBranchModel, "expect")
    expect_case_branch = branch_subquery(Case, "expect__case")

    return qs.annotate(
        agent_branch_id=Subquery(agent_branch.values("id")[:1]),
        agent_branch_name=Subquery(agent_branch.values("name")[:1]),
        case_branch_id=Subquery(case_branch.values("id")[:1]),
        case_branch_name=Subquery(case_branch.values("name")[:1]),
        expect_branch_name=Subquery(expect_branch.values("name")[:1]),
        expect_case_branch_id=Subquery(expect_case_branch.values("id")[:1]),
    )
