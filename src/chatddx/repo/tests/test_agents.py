import pytest

from chatddx.core.models import IdentityModel
from chatddx.django.orm.qs import qs_canon
from chatddx.repo.bundles import bundle_of
from chatddx.repo.shufflers.agent import select_agents_async


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_load_agents_by_output_type_title(
    inventory_fixture_commit: object,
    owner: IdentityModel,
):
    _ = inventory_fixture_commit

    model_cls = bundle_of("agent").branch_model

    qs = qs_canon(model_cls.objects.all(), owner.name)

    agents_output_type_1 = await select_agents_async(
        owner_name=owner.name,
        qs=qs.filter(target__output_type__definition__title="output_type-1"),
    )

    agents_output_type_2 = await select_agents_async(
        owner_name=owner.name,
        qs=qs.filter(target__output_type__definition__title="output_type-2"),
    )

    assert len(agents_output_type_1) == 2
    assert len(agents_output_type_2) == 1
