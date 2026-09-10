from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from ninja import NinjaAPI, Schema
from pydantic_ai.exceptions import ModelHTTPError

from chatddx.core.choices import SessionContextChoices
from chatddx.core.models import IdentityModel
from chatddx.history.session import start_session
from chatddx.repo.shufflers.agent import (
    load_agents_async,
)
from chatddx.repo.shufflers.main import (
    ensure_identity,
    load_branch_async,
)
from chatddx.runtime.runners import run_from_session

api = NinjaAPI(title="ChatDDx Swift API", version="1.0.0")
User = get_user_model()


class SwiftDiagnoseRequest(Schema):
    symptoms: str
    model: str


class ModelOptionResponse(Schema):
    value: str
    label: str


def get_authenticated_username(request: HttpRequest) -> IdentityModel:
    if not request.user or request.user.is_anonymous:
        username = "guest"
    else:
        username = request.user.username

    owner = ensure_identity(username)

    return owner


@api.get("/agents", response=list[ModelOptionResponse])
async def get_agents_endpoint(request: HttpRequest, output_type: str | None = None):
    owner = await sync_to_async(get_authenticated_username)(request)

    agents = await load_agents_async(owner_name=owner.name, output_type=output_type)

    options = [{"value": agent.name, "label": agent.name} for agent in agents]

    return options


@api.post("/diagnose")
async def swift_diagnose_endpoint(request: HttpRequest, payload: SwiftDiagnoseRequest):
    owner = await sync_to_async(get_authenticated_username)(request)

    try:
        agent = await load_branch_async(
            bundle_name="agent",
            owner_name=owner.name,
            branch_name=payload.model,
        )

        if not agent:
            raise ValueError(f"No configuration branch found named '{payload.model}'")

        agent_spec = agent.target

    except Exception as e:
        return api.create_response(
            request,
            {
                "error": f"could not load model '{payload.model}' found registered for user '{owner.name}'. Detail: {e}"
            },
            status=400,
        )

    api_key = owner.secrets.get("api-keys", {}).get(agent.name)
    session = await start_session(owner.pk, agent.id, SessionContextChoices.CHAT)

    try:
        run_result = await run_from_session(
            session=session,
            prompt=payload.symptoms,
            agent_spec=agent_spec,
            api_key=api_key,
        )
        return run_result.output

    except ModelHTTPError as e:
        error_message = "An upstream model error occurred."
        if isinstance(e.body, dict) and "message" in e.body:
            error_message = e.body["message"]
        elif hasattr(e, "message"):
            error_message = e.message

        return api.create_response(
            request,
            {"error": error_message},
            status=400,
        )
    except Exception as e:
        return api.create_response(
            request,
            {"error": f"Execution error: {str(e)}"},
            status=500,
        )
