# src/chatddx/repl.py
import asyncio
from typing import Annotated, Any

import typer
from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from pydantic_ai import (
    AgentRunResultEvent,
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    OutputToolCallEvent,
    OutputToolResultEvent,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from rich.console import Console

from chatddx.history.models import SessionModel
from chatddx.history.schemas import SessionSpec
from chatddx.history.session import refresh_messages, resume_session, start_session
from chatddx.repo.base import BranchSpec
from chatddx.repo.branch_models import AgentBranchModel
from chatddx.repo.branch_spec import AgentBranchSpec
from chatddx.repo.shufflers.agent import load_agent
from chatddx.repo.shufflers.main import ensure_identity
from chatddx.repo.trail_specs import AgentSpec
from chatddx.runtime.runners import stream_from_session

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def main(
    owner_name: Annotated[str, typer.Argument()],
    session_uuid: Annotated[str | None, typer.Option("--session")] = None,
    agent_name: Annotated[str | None, typer.Option("--agent")] = None,
):
    """
    Start a repl with an agent
    """

    owner = ensure_identity(owner_name)

    if session_uuid is None and agent_name is None:
        typer.echo("Error: You must provide either --session or --agent or both.")
        typer.secho("\nAvailable agents:", bold=True)
        for agent in AgentBranchModel.objects.filter(owner_id=owner.pk):
            typer.echo(agent.name)

        typer.secho("\nAvailable sessions:", bold=True)
        for db_session in SessionModel.objects.filter(owner_id=owner.pk):
            default_agent_name = (
                db_session.default_agent.name if db_session.default_agent else "?"
            )
            typer.echo(
                f"{db_session.uuid} {db_session.timestamp.strftime('%Y-%m-%d %H:%M')} {default_agent_name} {len(db_session.messages.all())}"
            )

        return

    session: SessionSpec | None = None
    agent_branch: BranchSpec[AgentSpec] | None = None

    if session_uuid:
        session = asyncio.run(resume_session(owner.pk, session_uuid))
        if not agent_name:
            agent_branch = session.default_agent

    if agent_name:
        agent_branch = load_agent(owner.name, agent_name)
        assert agent_branch is not None
        if not session_uuid:
            session = asyncio.run(start_session(owner.pk, agent_branch.id))

    assert session is not None
    assert agent_branch is not None

    run_repl(session, agent_branch)


def run_repl(session: SessionSpec, agent_branch: BranchSpec[AgentSpec]):
    agent_spec = agent_branch.target
    agent_name = agent_branch.name
    print(f"session id: {session.uuid}")
    print(f"agent: {agent_name}")

    for message in session.messages:
        if not isinstance(message.payload, (ModelRequest, ModelResponse)):
            continue

        msg_agent = AgentBranchModel.objects.filter(
            owner_id=session.owner_id,
            target_id=message.agent_id,
        ).first()
        if msg_agent is None:
            continue

        print_message(message.payload, msg_agent.name, msg_agent.target)

    async def consume_and_print(user_prompt: str):
        console.print(agent_name, style="#FFFFFF")

        stream_gen = stream_from_session(
            session,
            user_prompt,
            agent_spec=agent_spec,
        )

        thinking_started = False
        async for event in stream_gen:
            match event:
                case PartStartEvent(part=TextPart(content=text)):
                    console.print(text, end="", style="#886622")
                case PartDeltaEvent(delta=TextPartDelta(content_delta=text)):
                    console.print(text, end="", style="#886622")
                case PartStartEvent(part=ThinkingPart(content=text)):
                    if not thinking_started:
                        console.print("Thinking:", end=" ", style="#226688")
                        thinking_started = True
                    console.print(text, end="", style="#226688")
                case PartDeltaEvent(delta=ThinkingPartDelta(content_delta=text)) if (
                    text
                ):
                    console.print(text, end="", style="#226688")
                case FunctionToolCallEvent(part=part) | OutputToolCallEvent(part=part):
                    console.print(
                        f"\n<tool call: {part.tool_name}({part.args})>",
                        style="#662288",
                    )
                case (
                    FunctionToolResultEvent(part=part)
                    | OutputToolResultEvent(part=part)
                ):
                    console.print(
                        f"<tool result ({part.tool_name}): {part.content}>",
                        style="#662288",
                    )
                case (
                    PartStartEvent()
                    | PartDeltaEvent()
                    | PartEndEvent()
                    | FinalResultEvent()
                    | AgentRunResultEvent()
                ):
                    pass
                case _:
                    raise ValueError(f"No handler for {type(event)}")
        print()

    while True:
        prompt_ = prompt(
            "> ",
            history=FileHistory("history.txt"),
            auto_suggest=AutoSuggestFromHistory(),
        )
        asyncio.run(consume_and_print(prompt_))
        asyncio.run(refresh_messages(session))


def print_message(
    message: ModelMessage,
    name: str,
    agent: AgentSpec,
    skip_text: bool = False,
):
    content: list[tuple[str, str]] = []
    assert message.timestamp

    if not skip_text:
        content.extend(
            [
                (name, "#FFFFFF"),
                (f"======{message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}======", ""),
            ]
        )

    kind = message.kind
    for part in message.parts:
        match kind, part:
            case "response", ThinkingPart():
                content.append((part.content, "#226688"))
            case "response", TextPart():
                if not skip_text:
                    content.append((part.content, "#886622"))
            case "request", UserPromptPart():
                content.append((str(part.content), "#882266"))
            case "response", ToolCallPart():
                content.append((str(part), "#662288"))
            case "request", ToolReturnPart():
                content.append((str(part), "#662288"))
            case _:
                raise ValueError(f"unhandled kind-part tuple ({kind}, {type(part)})")

    for s, c in content:
        console.print(s, style=c)
