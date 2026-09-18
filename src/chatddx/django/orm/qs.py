# pyright: basic
from django.db.models import (
    Count,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
)

from chatddx.history.models import ExperimentModel
from chatddx.history.proxies import Message
from chatddx.repo.bundles import bundle_of
from chatddx.repo.entities.agent.django import Agent
from chatddx.repo.entities.case.django import Case
from chatddx.repo.entities.expect.django import Expect, ExpectBranchModel
from chatddx.repo.families.django import BranchModel, TrailModel
from chatddx.repo.registry import EntityName
from chatddx.repo.todo import agent_relations


def qs_super_agent[T: BranchModel](qs: QuerySet[T], owner_name: str):
    def subquery(owner_name: str, model: EntityName, column: str):
        branch_model_cls = bundle_of(model).branch_model

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


def qs_experiments(qs: QuerySet[ExperimentModel], owner_name: str):
    def branch_subquery(model: type[Agent | Case | Expect], target_field: str):
        return model.objects.filter(
            target=OuterRef(target_field),
            owner__name=owner_name,
        ).order_by("-timestamp")

    agent_branch = branch_subquery(Agent, "agent")
    case_branch = branch_subquery(Case, "case")
    expect_branch = branch_subquery(Expect, "expect")

    return qs.annotate(
        agent_branch_id=Subquery(agent_branch.values("id")[:1]),
        agent_branch_name=Subquery(agent_branch.values("name")[:1]),
        case_branch_id=Subquery(case_branch.values("id")[:1]),
        case_branch_name=Subquery(case_branch.values("name")[:1]),
        expect_branch_name=Subquery(expect_branch.values("name")[:1]),
        expect_branch_id=Subquery(expect_branch.values("id")[:1]),
    )
