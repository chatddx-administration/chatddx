from collections.abc import Sequence

from pydantic_ai import (
    ModelRequestPart,
    ModelResponsePart,
    NativeToolCallPart,
    NativeToolReturnPart,
    ToolAvailabilityDeltaPart,
    ToolCallPart,
    ToolReturnPart,
)


def get_part_content(
    parts: Sequence[ModelRequestPart | ModelResponsePart],
    PartType: type[ModelRequestPart | ModelResponsePart],
) -> str | None:
    content: list[str] = []
    for part in parts:
        if isinstance(part, PartType):
            if isinstance(part, (ToolCallPart, NativeToolCallPart)):
                # Tool calls carry structured args, not plain text content;
                # Message.tool_call reads them directly off the part instead.
                raise NotImplementedError(
                    f"unhandled part type '{type(part).__name__}'"
                )
            elif isinstance(part, (ToolReturnPart, NativeToolReturnPart)):
                # Tool returns can carry structured content, not just plain
                # text; Message.tool_return reads them directly off the part
                # instead.
                raise NotImplementedError(
                    f"unhandled part type '{type(part).__name__}'"
                )
            elif isinstance(part, ToolAvailabilityDeltaPart):
                raise NotImplementedError(
                    f"unhandled part type '{type(part).__name__}'"
                )
            else:
                match part.content:
                    case str():
                        content.append(part.content)
                    case _:
                        raise NotImplementedError(
                            f"unhandled part type '{type(part.content)}'"
                        )
    if not content:
        return None

    if len(content) != 1:
        raise NotImplementedError(
            f"can only handle one piece of content, got '{len(content)}'"
        )

    if content:
        return content[0]
