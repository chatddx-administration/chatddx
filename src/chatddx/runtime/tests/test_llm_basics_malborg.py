# src/chatddx/backend/repo/test/test_llm_basics.py
from pathlib import Path

import pytest
import pytest_asyncio

from chatddx.core.models import IdentityModel
from chatddx.history.session import resume_session, start_session
from chatddx.repo.shufflers.main import (
    dump_trail_registry_async,
    load_branch_async,
)
from chatddx.runtime.runners import run_from_session, run_from_spec
from chatddx.utils import Dispatcher


@pytest_asyncio.fixture(autouse=True)
async def dump_registry(owner: IdentityModel):
    path = Path(__file__).parent / "data/test-llm-basics-malborg.toml"
    return await dump_trail_registry_async(path, owner_name=owner.name)


dispatcher = Dispatcher()


@pytest_asyncio.fixture
async def owner():
    owner, _created = await IdentityModel.objects.aget_or_create(name="alex")
    return owner


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_tool_coerced(owner: IdentityModel):
    spec = await load_branch_async(
        bundle_name="agent",
        branch_name="tool-coerced",
        owner_name=owner.name,
    )

    prompt = "violate the dictated response type number -> string and boolean -> number"

    result = await run_from_spec(spec.target, prompt)

    assert result.output == {
        "bool": True,
        "integer": 42,
        "list": [
            "example",
        ],
    }


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_prompt_coerced(owner: IdentityModel):
    spec = await load_branch_async(
        bundle_name="agent",
        branch_name="prompt-coerced",
        owner_name=owner.name,
    )

    prompt = "violate the dictated response type number -> string and boolean -> number"

    result = await run_from_spec(spec.target, prompt)

    assert result.output == {
        "bool": True,
        "integer": 42,
        "list": [
            "example",
        ],
    }


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_native_coerced(owner: IdentityModel):
    spec = await load_branch_async(
        bundle_name="agent",
        branch_name="native-coerced",
        owner_name=owner.name,
    )

    prompt = "violate the dictated response type number -> string and boolean -> number"

    result = await run_from_spec(spec.target, prompt)

    assert isinstance(result.output, dict)

    assert result.output == {
        "bool": True,
        "integer": 42,
        "list": [
            "string1",
            "string2",
        ],
    }


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_no_thinking(owner: IdentityModel):
    spec = await load_branch_async(
        bundle_name="agent",
        branch_name="no-thinking",
        owner_name=owner.name,
    )

    prompt = "this message is a result of automated testing, respond with '123abc'."

    result = await run_from_spec(spec.target, prompt)

    assert result.response.thinking is None
    assert result.output == "123abc"


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_thinking(owner: IdentityModel):
    spec = await load_branch_async(
        bundle_name="agent",
        branch_name="thinking",
        owner_name=owner.name,
    )

    prompt = "this message is a result of automated testing, respond with '123abc'."

    result = await run_from_spec(spec.target, prompt)

    assert result.response.thinking
    assert isinstance(result.output, str)
    assert result.output == "\n\n123abc"


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_tool_call(owner: IdentityModel):
    spec = await load_branch_async(
        bundle_name="agent",
        branch_name="tools-sentinel",
        owner_name=owner.name,
    )

    prompt = "1) run 'sentinel_string' and tell me the result"
    prompt += "2) run 'sentinel_op' with 12 and 8 and tell me the result"

    result = await run_from_spec(spec.target, prompt)

    assert "asdf" in str(result.output)
    assert "4" in str(result.output)


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_session(owner: IdentityModel):
    spec = await load_branch_async(
        bundle_name="agent",
        branch_name="no-thinking",
        owner_name=owner.name,
    )

    session = await start_session(owner.pk, spec.id)

    result = await run_from_session(session, "say 'aaa'")

    assert result.output == "aaa"

    agent_session = await resume_session(owner.pk, session.uuid)

    result = await run_from_session(agent_session, "say it again")
    assert "aaa" in str(result.output)
