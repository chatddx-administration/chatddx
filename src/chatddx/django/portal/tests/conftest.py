# pyright: basic
from typing import Any

import pytest
from django.test import Client
from pytest_django import DjangoDbBlocker

from chatddx.conftest import Provision, _init_data
from chatddx.core import settings
from chatddx.repo.entities.case.pydantic import CaseBranchDetails
from chatddx.repo.store.branch import commit, select_visible_branch_models


def started(provision: Provision, user: str) -> None:
    """
    `user` as the portal takes an owner on: the giftbag, and the test cases
    as their own, as an import of the archive's would give them.
    """
    _ = provision("--with-giftbag", user=user)

    for case in select_visible_branch_models("case", settings.ARCHIVE_IDENTITY_NAME):
        _ = commit(
            case.trail,
            CaseBranchDetails.model_validate(
                {
                    **case.details,
                    "name": case.name,
                    "owner": user,
                    "tags": [tag.name for tag in case.tags.all()],
                }
            ),
        )


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup: None, django_db_blocker: DjangoDbBlocker) -> None:
    # the portal shows an owner their own: the seed gives alice hers
    with django_db_blocker.unblock():
        started(_init_data, "alice")


@pytest.fixture
def alice(client: Client, django_user_model: Any) -> Client:
    """alice's session in the portal, on what the seed gave her."""
    client.force_login(django_user_model.objects.create_superuser(username="alice"))
    return client


@pytest.fixture
def bob(django_user_model: Any, provision: Provision) -> Client:
    """bob's session, beside alice's, started as she was."""
    started(provision, "bob")
    client = Client()
    client.force_login(django_user_model.objects.create_superuser(username="bob"))
    return client
