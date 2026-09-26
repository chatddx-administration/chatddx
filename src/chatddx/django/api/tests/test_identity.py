# pyright: basic
from collections.abc import Callable
from typing import Any

import pytest
from django.test import Client

from chatddx.core.models import IdentityModel

pytestmark = pytest.mark.django_db


def test_a_session_acts_as_its_user_s_identity(alex: Client):
    response = alex.get("/api/me")

    assert response.json() == {"name": "alex", "guest": False}
    assert "csrftoken" in response.cookies


def test_a_request_without_a_session_acts_as_the_guest(client: Client):
    assert client.get("/api/me").json() == {"name": "guest", "guest": True}
    assert IdentityModel.objects.filter(name="guest").exists()


def test_a_user_s_identity_is_made_when_it_is_first_met(
    client: Client, django_user_model: Any
):
    client.force_login(django_user_model.objects.create_user(username="sam"))

    assert client.get("/api/me").json()["name"] == "sam"
    assert IdentityModel.objects.filter(name="sam").exists()


def test_a_session_s_unsafe_requests_carry_its_csrf_token(django_user_model: Any):
    browser = Client(enforce_csrf_checks=True)
    browser.force_login(django_user_model.objects.create_user(username="alex"))
    save = {"configuration": "free-text", "name": "mine"}

    refused = browser.post("/api/cell/save", save, content_type="application/json")

    assert refused.status_code == 403
    assert "CSRF" in refused.json()["detail"]

    token = browser.get("/api/me").cookies["csrftoken"].value
    saved = browser.post(
        "/api/cell/save", save, content_type="application/json", HTTP_X_CSRFTOKEN=token
    )

    assert saved.status_code == 200, saved.content


def test_the_guest_s_requests_need_no_token(provision: Callable[..., None]):
    provision(user="guest")
    stranger = Client(enforce_csrf_checks=True)

    saved = stranger.post(
        "/api/cell/save",
        {"configuration": "free-text", "name": "mine"},
        content_type="application/json",
    )

    assert saved.status_code == 200, saved.content
    assert saved.json()["configuration"]["owner"]["name"] == "guest"


def test_no_identity_s_secrets_are_shown(alex: Client):
    archive = IdentityModel.objects.get(name="archive")
    archive.secrets = {"key": "sesame"}
    archive.save()

    for path in ("/api/registry/stack", "/api/registry/case/case-1", "/api/me"):
        assert "sesame" not in alex.get(path).content.decode()


def test_the_api_describes_itself(client: Client):
    described = client.get("/api/openapi.json")
    paths = described.json()["paths"]
    run = paths["/api/runs"]["post"]["responses"]["200"]
    batch = paths["/api/batch"]["post"]["responses"]["200"]
    events = described.json()["components"]["schemas"]["Event"]

    assert described.status_code == 200
    assert {"/api/runs", "/api/cell", "/api/registry/case/{name}"} <= set(paths)
    assert set(run["content"]) == {"application/json", "text/event-stream"}
    assert set(batch["content"]) == {"text/event-stream"}
    assert {"batch", "run", "recorded", "summary"} <= set(
        events["discriminator"]["mapping"]
    )
    assert client.get("/api/docs").status_code == 200
