# src/chatddx/history/session.py
from uuid import UUID

from asgiref.sync import sync_to_async

from chatddx.core.models import IdentityModel
from chatddx.core.schemas import IdentitySpec
from chatddx.history.models import MessageModel, SessionModel
from chatddx.history.schemas import MessageSpec, SessionSpec
from chatddx.repo.branch_models import AgentBranchModel
from chatddx.repo.shufflers.main import resolve_related_array_fields_async


async def get_identity(name: str) -> IdentitySpec:
    identity = await IdentityModel.objects.aget(name=name)
    return IdentitySpec.model_validate(identity)


async def start_session(
    owner_id: int,
    agent_id: int,
    description: str | None = None,
) -> SessionSpec:

    session_model = await SessionModel.objects.acreate(
        owner_id=owner_id,
        default_agent_id=agent_id,
        description=description,
    )

    return await resume_session(owner_id, session_model.uuid)


async def resume_session(
    owner_id: int,
    uuid: UUID | str,
    default_agent: AgentBranchModel | None = None,
) -> SessionSpec:

    session_model = (
        await SessionModel.objects.select_related("default_agent")
        .prefetch_related("messages", "default_agent__collaborators")
        .aget(
            uuid__startswith=uuid,
            owner_id=owner_id,
        )
    )

    if default_agent:
        session_model.default_agent = default_agent

    if session_model.default_agent is None:
        raise ValueError("Cannot resume a session without an agent")

    target_attr = await sync_to_async(lambda: session_model.default_agent.target)()

    session_model.default_agent.target = await resolve_related_array_fields_async(
        session_model.default_agent.target
    )

    return SessionSpec.model_validate(session_model)


async def refresh_messages(
    session: SessionSpec,
) -> None:
    queryset = MessageModel.objects.select_related().filter(session_id=session.id)

    if len(session.messages) > 0:
        queryset = queryset.filter(pk__gt=session.messages[-1].id)

    session.messages.extend([MessageSpec.model_validate(m) async for m in queryset])
