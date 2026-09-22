from typing import Literal

type EntityName = Literal[
    "instruction",
    "connection",
    "sampling_params",
    "output_type",
    "tool",
    "tool_group",
    "agent",
    "scorer",
    "expect",
    "case",
]

type ViewName = EntityName | Literal["super_agent"]
