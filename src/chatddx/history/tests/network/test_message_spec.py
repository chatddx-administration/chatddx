"""Verifies the shape of pydantic-ai message specs recorded from a real run.

Requires network access to the endpoint configured in
data/test-llm-basics.toml.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio

from chatddx.core.models import IdentityModel
from chatddx.repo.shufflers.main import (
    dump_trail_registry_async,
    load_branch_async,
)
from chatddx.runtime.runners import run_from_spec

pytestmark = pytest.mark.network


@pytest_asyncio.fixture(autouse=True)
async def dump_registry(owner: IdentityModel):
    path = Path(__file__).parent / "data/test-llm-basics.toml"
    return await dump_trail_registry_async(path, owner_name=owner.name)


@pytest_asyncio.fixture
async def owner():
    owner, _created = await IdentityModel.objects.aget_or_create(name="alex")
    return owner


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_message_spec(owner: IdentityModel):
    spec = await load_branch_async(
        bundle_name="agent",
        branch_name="no-thinking",
        owner_name=owner.name,
    )
    assert spec.target.connection

    prompt = "hello"
    result = await run_from_spec(spec.target, prompt)

    messages = json.loads(result.new_messages_json())

    req_msg, res_msg = messages

    assert list(req_msg.keys()) == [
        "parts",
        "timestamp",
        "instructions",
        "kind",
        "run_id",
        "conversation_id",
        "metadata",
    ]
    assert list(res_msg.keys()) == [
        "parts",
        "usage",
        "model_name",
        "timestamp",
        "kind",
        "provider_name",
        "provider_url",
        "provider_details",
        "provider_response_id",
        "finish_reason",
        "run_id",
        "conversation_id",
        "metadata",
        "state",
    ]

    assert req_msg["kind"] == "request"
    assert res_msg["kind"] == "response"

    assert res_msg["run_id"] == req_msg["run_id"]

    (req_part,) = req_msg["parts"]
    (res_part,) = res_msg["parts"]

    assert list(req_part.keys()) == [
        "content",
        "timestamp",
        "part_kind",
    ]

    assert list(res_part.keys()) == [
        "content",
        "id",
        "provider_name",
        "provider_details",
        "part_kind",
    ]

    assert req_part["part_kind"] == "user-prompt"
    assert res_part["part_kind"] == "text"

    assert req_part["content"] == prompt
    assert res_part["content"] == result.output

    assert req_msg["metadata"] is None
    assert res_msg["metadata"] is None

    # ModelResponse only
    assert res_part["id"] is None
    assert res_part["provider_name"] is None
    assert res_part["provider_details"] is None
    assert res_msg["provider_name"] == "openai"
    assert res_msg["provider_url"] == str(spec.target.connection.endpoint)
    assert res_msg["model_name"] == spec.target.connection.model
    assert res_msg["finish_reason"] == "stop"

    res_usage = res_msg["usage"]
    assert list(res_usage.keys()) == [
        "input_tokens",
        "cache_write_tokens",
        "cache_read_tokens",
        "output_tokens",
        "input_audio_tokens",
        "cache_audio_read_tokens",
        "output_audio_tokens",
        "details",
    ]

    assert res_usage["input_tokens"] == 13
    assert res_usage["output_tokens"] == 12
    assert res_usage["cache_read_tokens"] == 0
    assert res_usage["cache_write_tokens"] == 0
    assert res_usage["details"] == {}

    res_provider = res_msg["provider_details"]
    assert list(res_provider.keys()) == [
        "finish_reason",
        "timestamp",
    ]

    assert res_provider["finish_reason"] == "stop"

    req_msg_t = datetime.fromisoformat(req_msg["timestamp"])
    res_msg_t = datetime.fromisoformat(res_msg["timestamp"])
    assert req_msg_t < res_msg_t

    req_part_t = datetime.fromisoformat(req_part["timestamp"])
    assert req_part_t < req_msg_t

    res_provider_t = datetime.fromisoformat(res_provider["timestamp"])
    assert res_provider_t < res_msg_t
