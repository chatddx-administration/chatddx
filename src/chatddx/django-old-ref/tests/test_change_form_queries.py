# pyright: basic

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from chatddx.core.models import IdentityModel
from chatddx.repo.inventories import InventoryBranchModel

pytestmark = [pytest.mark.django_db(transaction=True)]

BUDGET = {
    "tool": 30,
    "connection": 30,
    "case": 40,
    "agent": 50,
    "super_agent": 70,
}


def count_queries(client: Client, url: str) -> int:
    assert client.get(url).status_code == 200

    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200

    return len(ctx.captured_queries)


@pytest.mark.parametrize("page", sorted(BUDGET))
def test_a_change_form_stays_within_its_query_budget(
    page: str,
    user_client: Client,
    inventory_fixture_bm: InventoryBranchModel,
    owner: IdentityModel,
):
    entity = "agent" if page == "super_agent" else page
    branch = next(iter(inventory_fixture_bm[entity].values()))

    url = reverse(f"admin:orm_{page.replace('_', '')}_change", args=(branch.pk,))
    queries = count_queries(user_client, url)

    assert queries <= BUDGET[page], (
        f"the {page} change form now costs {queries} queries, "
        f"over its budget of {BUDGET[page]}"
    )


def test_a_plain_change_form_does_not_pay_for_the_agent_form(
    user_client: Client,
    inventory_fixture_bm: InventoryBranchModel,
    owner: IdentityModel,
):
    tool = next(iter(inventory_fixture_bm["tool"].values()))
    agent = next(iter(inventory_fixture_bm["agent"].values()))

    tool_queries = count_queries(
        user_client, reverse("admin:orm_tool_change", args=(tool.pk,))
    )
    agent_queries = count_queries(
        user_client, reverse("admin:orm_superagent_change", args=(agent.pk,))
    )

    assert tool_queries < agent_queries
