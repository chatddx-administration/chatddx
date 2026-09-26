# pyright: basic
from typing import Any

import pytest
from django.test import Client

from chatddx.conftest import Provision


@pytest.fixture
def alice(client: Client, django_user_model: Any) -> Client:
    """alice's session in the portal, on the test inventory the seed gave her."""
    client.force_login(django_user_model.objects.create_superuser(username="alice"))
    return client


@pytest.fixture
def bob(django_user_model: Any, provision: Provision) -> Client:
    """bob's session, beside alice's, on the test inventory too."""
    _ = provision(user="bob")
    client = Client()
    client.force_login(django_user_model.objects.create_superuser(username="bob"))
    return client
