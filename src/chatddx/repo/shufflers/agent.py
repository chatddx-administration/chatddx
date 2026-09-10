from chatddx.django.orm.qs import qs_canon
from chatddx.repo.base import BranchModel
from chatddx.repo.main import Repo
from chatddx.repo.shufflers.main import load_branch, load_branches
from chatddx.utils import make_async


def load_agent(
    owner_name: str,
    branch_name: str,
    output_type: str | None = None,
):
    model_cls = Repo("agent", BranchModel)
    qs = model_cls.objects.filter(name=branch_name)
    if output_type:
        qs = qs.filter(target__output_type__fingerprint=output_type)

    return load_branch(
        bundle_name="agent",
        owner_name=owner_name,
        qs=qs,
    )


load_agent_async = make_async(load_agent)


def load_agents(
    owner_name: str,
    output_type: str | None = None,
):

    model_cls = Repo("agent", BranchModel)
    qs = qs_canon(model_cls.objects.all(), owner_name)

    qs = qs.filter(target__output_type__definition__title=output_type)

    return load_branches(
        bundle_name="agent",
        owner_name=owner_name,
        qs=qs,
    )


load_agents_async = make_async(load_agents)
