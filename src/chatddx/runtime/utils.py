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
                content.append(f"{part.tool_name}: {part.args_as_json_str()}")
            elif isinstance(part, (ToolReturnPart, NativeToolReturnPart)):
                content.append(f"{part.tool_name}: {part.content}")
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
