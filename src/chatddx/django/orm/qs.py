from django.db.models import (
    Count,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
)

from chatddx.experiment.proxies import Experiment
from chatddx.history.proxies import Message
from chatddx.repo.base import BranchModel, TrailModel
from chatddx.repo.branch_models import ExpectBranchModel
from chatddx.repo.main import Repo, agent_relations
from chatddx.repo.proxies import Agent, Case


def qs_super_agent[T: BranchModel](qs: QuerySet[T], owner_name: str):
    def subquery(owner_name: str, model: str, column: str):
        branch_model_cls = Repo(model, BranchModel)

        return branch_model_cls.objects.filter(
            target=OuterRef(f"target__{model}"),
            owner__name=owner_name,
        ).values(column)[:1]

    branch_annotations = {
        f"{model}_{field}": Subquery(subquery(owner_name, model, field))
        for field in ("name", "id")
        for model in agent_relations
    }
    return qs.select_related(
        *[f"target__{model}" for model in agent_relations]
    ).annotate(**branch_annotations)


def qs_owned_trails[T: TrailModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    return (
        qs.filter(branches__owner__name=owner_name)
        .annotate(branch_name=F("branches__name"))
        .order_by("id")
        .distinct("id")
    )


def qs_canon[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    owned_qs = qs.filter(owner__name=owner_name)

    count_subquery = (
        qs.filter(owner_id=OuterRef("owner_id"), name=OuterRef("name"))
        .values("owner_id", "name")
        .annotate(total=Count("id"))
        .values("total")
    )

    canonical_ids = (
        owned_qs.order_by("owner_id", "name", "-timestamp")
        .distinct("owner_id", "name")
        .values_list("id", flat=True)
    )

    return (
        owned_qs.filter(id__in=canonical_ids)
        .annotate(_version_count=Subquery(count_subquery))
        .order_by("-timestamp")
    )


def qs_canon_col[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    owned_qs = qs.filter(Q(owner__name=owner_name) | Q(collaborators__name=owner_name))

    count_subquery = (
        qs.filter(owner_id=OuterRef("owner_id"), name=OuterRef("name"))
        .values("owner_id", "name")
        .annotate(total=Count("id"))
        .values("total")
    )

    canonical_ids = (
        owned_qs.order_by("owner_id", "name", "-timestamp")
        .distinct("owner_id", "name")
        .values_list("id", flat=True)
    )

    return (
        owned_qs.filter(id__in=canonical_ids)
        .annotate(_version_count=Subquery(count_subquery))
        .order_by("-timestamp")
    )


def qs_owned[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    return qs.filter(owner__name=owner_name)


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
