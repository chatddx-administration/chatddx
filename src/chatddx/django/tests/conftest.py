from typing import Any

import pytest
from django.contrib.auth.models import User
from django.test.client import Client

from chatddx.core.choices import SessionContextChoices
from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identity
from chatddx.history.models import ExperimentModel, RunModel, SessionModel
from chatddx.repo.inventories import InventoryBranchModel, InventoryFormDataOut


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
    case = inventory_fixture_bm["case"]["case-1"].target
    agent = inventory_fixture_bm["agent"]["agent-2"].target

    return ExperimentModel.objects.create(
        owner=owner,
        agent=agent,
        case=case,
        expect=case.expects.first(),
        tags="baseline",
        scorer=case.expects.first().scorer,
    )


@pytest.fixture
def shared_experiment(
    other_owner: IdentityModel,
    owner: IdentityModel,
    collaborators: list[IdentityModel],
    inventory_fixture_bm: InventoryBranchModel,
):
    case = inventory_fixture_bm["case"]["case-1"].target
    agent = inventory_fixture_bm["agent"]["agent-2"].target

    experiment = ExperimentModel.objects.create(
        owner=other_owner,
        agent=agent,
        case=case,
        expect=case.expects.first(),
        tags="shared-with-me",
        scorer=case.expects.first().scorer,
    )

    experiment.collaborators.set(collaborators + [owner])

    return experiment


@pytest.fixture
def run(owner: IdentityModel, experiment: ExperimentModel):
    return RunModel.objects.create(owner=owner, experiment=experiment)
