# pyright: basic
from pathlib import Path

import pytest
from django.contrib.auth.models import User as DjangoUser
from ninja.testing import TestAsyncClient

from chatddx.core.models import IdentityModel
from chatddx.django.api import api
from chatddx.repo.shufflers.main import dump_trail_registry


@pytest.fixture(autouse=True)
def branch_registry(owner: IdentityModel):
    path = Path(__file__).parent / "data/test-registry.toml"
    return dump_trail_registry(path, owner_name=owner.name)


@pytest.fixture
def owner(admin_user: DjangoUser):
    owner, _created = IdentityModel.objects.get_or_create(name=admin_user.username)
    return owner


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_swift_diagnose_endpoint_success(branch_registry, admin_user):
    client = TestAsyncClient(api)

    response = await client.post(
        "/diagnose",
        json={
            "symptoms": "Severe acute migratory right lower quadrant abdominal pain for 12 hours.",
            "model": "swift",
        },
        user=admin_user,
    )

    assert response.status_code == 200
    data = response.json()
    # (Path(__file__).parent / "data/responses/swift.json").write_text(json.dumps(data))

    assert (
        data["acute_warning"]
        == "This presentation is concerning for acute appendicitis, which can rapidly progress to perforation and peritonitis, leading to sepsis and potentially life-threatening complications. Immediate evaluation and intervention are essential."
    )
    assert len(data["diagnoses"]) == 5
    assert data["diagnoses"][0]["diagnosis"] == "Acute Appendicitis"
    assert (
        data["management"]["disposition"]
        == "The patient should be evaluated in the emergency department for prompt diagnosis and management. If appendicitis is confirmed, surgical consultation is necessary. If the diagnosis is uncertain, further imaging and observation may be required. In cases of complications such as perforation or suspected ectopic pregnancy, immediate intervention is critical."
    )
