# pyright: basic
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.test.client import Client

from chatddx.core.choices import SessionContextChoices
from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identity
from chatddx.history.models import ExperimentModel, RunModel, SessionModel
from chatddx.repo.entities.agent.django import AgentBranchModel
from chatddx.repo.entities.expect.django import ExpectBranchModel
from chatddx.repo.entities.expect.pydantic import ExpectTrailSchema
from chatddx.repo.entities.output_type.pydantic import OutputTypeTrailSchema
from chatddx.repo.entities.scorer.pydantic import ScorerTrailSchema
from chatddx.repo.families.pydantic import BranchSchemaDetails
from chatddx.repo.inventories import (
    InventoryBranchModel,
    InventoryFormDataOut,
    ParsedInventory,
)
from chatddx.repo.shufflers.branch import commit

# The name the owner gives the one scorer of theirs whose code exists: the
# test inventory's scorers name commands nothing implements.
RANKED = "reciprocal_rank"


@pytest.fixture
def user_client(client: Client, django_user_model: User):
    django_user = django_user_model.objects.create_superuser(
        username="alex",
        email="alex@kompismoln.se",
        password="password",
    )
    client.force_login(django_user)

    return client


@pytest.fixture
def session(owner: IdentityModel) -> SessionModel:
    return SessionModel.objects.create(
        owner=owner,
        context=SessionContextChoices.CHAT,
        description="a session",
    )


@pytest.fixture
def collaborators() -> list[IdentityModel]:
    return [
        ensure_identity("collaborator-1"),
        ensure_identity("collaborator-2"),
    ]


@pytest.fixture
def superagent_post_data(inventory_fixture_fdo: InventoryFormDataOut) -> dict[str, Any]:
    post_data_relations: dict[str, dict[str, Any]] = {
        "connection_": inventory_fixture_fdo.connection["some-connection"].model_dump(
            exclude_none=True
        ),
        "sampling_params_": inventory_fixture_fdo.sampling_params[
            "some-sampling_params"
        ].model_dump(exclude_none=True),
        "tool_group_": inventory_fixture_fdo.tool_group["some-tool_group"].model_dump(
            exclude_none=True
        ),
        "output_type_": inventory_fixture_fdo.output_type[
            "some-output_type"
        ].model_dump(exclude_none=True),
    }
    return inventory_fixture_fdo.agent["some-agent"].model_dump(exclude_none=True) | {
        f"{outer}{inner}": value
        for outer, inner_dict in post_data_relations.items()
        for inner, value in inner_dict.items()
    }


@pytest.fixture
def experiment(
    owner: IdentityModel,
    inventory_fixture_bm: InventoryBranchModel,
):
    case = inventory_fixture_bm["case"]["case-1"]
    agent = inventory_fixture_bm["agent"]["agent-2"].target
    expect_branch = case.expects.first()
    assert expect_branch is not None
    expect = expect_branch.target

    return ExperimentModel.objects.create(
        owner=owner,
        agent=agent,
        case=case.target,
        expect=expect,
    )


@pytest.fixture
def shared_experiment(
    other_owner: IdentityModel,
    owner: IdentityModel,
    collaborators: list[IdentityModel],
    inventory_fixture_bm: InventoryBranchModel,
):
    case = inventory_fixture_bm["case"]["case-1"]
    agent = inventory_fixture_bm["agent"]["agent-2"].target
    expect_branch = case.expects.first()
    assert expect_branch is not None
    expect = expect_branch.target

    experiment = ExperimentModel.objects.create(
        owner=other_owner,
        agent=agent,
        case=case.target,
        expect=expect,
    )

    experiment.collaborators.set(collaborators + [owner])

    return experiment


@pytest.fixture
def run(owner: IdentityModel, experiment: ExperimentModel):
    return RunModel.objects.create(owner=owner, experiment=experiment)


@pytest.fixture
def lister(parsed_inventory: ParsedInventory, owner: IdentityModel) -> AgentBranchModel:
    """agent-1, answering with a list of text rather than its own output type"""
    agent, _ = parsed_inventory.agent["agent-1"]
    listing = OutputTypeTrailSchema(
        definition={"type": "array", "items": {"type": "string"}},
    )

    _ = commit(
        trail=agent.model_copy(update={"output_type": listing}),
        branch_details=BranchSchemaDetails(name="lister", owner=owner.name),
    )

    return AgentBranchModel.objects.get(owner=owner, name="lister")


def ranked_expect(case_name: str, owner: IdentityModel) -> ExpectBranchModel:
    """
    An expectation for a case, judged by `reciprocal_rank` -- a scorer that
    reads a list of text and nothing else.
    """
    scorer = ScorerTrailSchema(command="reciprocal_rank")

    _ = commit(
        trail=scorer,
        branch_details=BranchSchemaDetails(name=RANKED, owner=owner.name),
    )
    _ = commit(
        trail=ExpectTrailSchema(payload="pneumonia", scorer=scorer),
        branch_details=BranchSchemaDetails(
            name=f"{case_name}|{RANKED}",
            owner=owner.name,
        ),
    )

    return ExpectBranchModel.objects.get(owner=owner, name=f"{case_name}|{RANKED}")
