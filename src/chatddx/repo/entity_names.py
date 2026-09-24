from typing import Literal

# In commit order: anything an entity references comes before it
# (new-datamodel.md §10), so committing in this order finds the branch an
# owner gave each part before a composition reaches it.
type EntityName = Literal[
    "machine",
    "os",
    "model",
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

# Every entity is presented through one view of its own name.
type ViewName = EntityName
