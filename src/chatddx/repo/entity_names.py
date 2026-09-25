from typing import Literal, get_args

type EntityName = Literal[
    "machine",
    "os",
    "llm",
    "serving",
    "client",
    "stack",
    "tool",
    "toolset",
    "instruction",
    "output",
    "coercion",
    "reasoning",
    "sampling",
    "configuration",
    "case",
    "scorer",
]

ENTITY_NAMES: tuple[EntityName, ...] = get_args(EntityName.__value__)

type PresentationName = EntityName
