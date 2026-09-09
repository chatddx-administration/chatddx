from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from django.contrib.auth.models import User as DjangoUser
from ninja.testing import TestAsyncClient
from pydantic_ai import AgentRunResult

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
@pytest.mark.skip(reason="Not implemented yet")
async def test_swift_diagnose_endpoint_success(branch_registry, admin_user):
    client = TestAsyncClient(api)

    mock_runtime_payload = {
        "acute_warning": "Immediate evaluation needed.",
        "diagnoses": [
            {
                "diagnosis": "Appendicitis",
                "probability": "high",
                "critical": True,
                "short_rationale": "Classic right lower quadrant presentation.",
            }
        ],
        "management": {
            "workup": [
                {
                    "type": "Radiology",
                    "investigations": ["Ultrasound abdomen"],
                    "priority": "urgent",
                }
            ],
            "empirical_treatment": [
                {
                    "indication": "Suspected inflammation",
                    "treatment": "IV Fluids and Antibiotics",
                    "important": "Keep NPO",
                }
            ],
            "disposition": "Admission",
        },
        "sources": ["UpToDate 2026"],
    }

    mock_result = AgentRunResult(output=mock_runtime_payload)

    with patch("chatddx.django.api.run_from_spec", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result

        response = await client.post(
            "/diagnose",
            json={
                "symptoms": "Severe acute migratory right lower quadrant abdominal pain for 12 hours.",
                "model": "swift",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["acute_warning"] == "Immediate evaluation needed."
        assert len(data["diagnoses"]) == 1
        assert data["diagnoses"][0]["diagnosis"] == "Appendicitis"
        assert data["management"]["disposition"] == "Admission"

        mock_run.assert_called_once()
        assert "symptoms" in mock_run.call_args[1].get("prompt")


@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.skip(reason="Not implemented yet")
async def test_swift_diagnose_endpoint_missing_model(admin_user):
    client = TestAsyncClient(api)
    admin_user.username = "alex"
    await admin_user.asave()

    response = await client.post(
        "/diagnose", json={"symptoms": "Nausea", "model": "non-existent-agent-branch"}
    )

    assert response.status_code == 404
    assert "error" in response.json()
