"""
The part of Handlebars chatddx's templates use, read without rendering them:
which variables a template places as values, and which it branches on.

Rendering is pydantic-ai's `TemplateStr` (pydantic-handlebars), at compile
time. What is checked here is what a template declares, when it is
committed: an instruction places every variable it declares and declares
every variable it places, and never branches on the case.
"""

import re
from dataclasses import dataclass, field

_MUSTACHE = re.compile(r"\{\{(?P<body>\{.*?\}|.*?)\}\}", re.DOTALL)
_BLOCK_HELPERS = frozenset({"if", "unless", "each", "with"})
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class TemplateError(ValueError):
    pass


@dataclass(frozen=True)
class Placements:
    # `{{name}}` and `{{{name}}}`: where a variable's value lands
    values: frozenset[str] = field(default_factory=frozenset)
    # `{{#if name}}`, `{{^name}}` and the like: what the template branches on
    conditions: frozenset[str] = field(default_factory=frozenset)

    def __or__(self, other: "Placements") -> "Placements":
        return Placements(
            values=self.values | other.values,
            conditions=self.conditions | other.conditions,
        )

    @property
    def names(self) -> frozenset[str]:
        return self.values | self.conditions


def placements(template: str) -> Placements:
    values: set[str] = set()
    conditions: set[str] = set()
    open_blocks: list[str] = []

    for match in _MUSTACHE.finditer(template):
        body = match.group("body")

        if body.startswith("{"):
            body = body[1:-1]

        body = body.strip("~").strip()

        if body.startswith("!"):
            continue

        if body == "else":
            if not open_blocks:
                raise TemplateError("{{else}} outside a block")
            continue

        if body.startswith(">"):
            raise TemplateError(
                f"{{{{{body}}}}}: a template is self-contained, it has no partials"
            )

        if body.startswith("/"):
            closed = body[1:].strip()

            if not open_blocks or open_blocks.pop() != closed:
                raise TemplateError(f"{{{{/{closed}}}}} closes nothing it opened")
            continue

        if body.startswith(("#", "^")):
            inverse = body.startswith("^")
            words = body[1:].split()

            if not words:
                raise TemplateError(f"{{{{{body}}}}} names nothing")

            if inverse:
                helper, arguments = "^", words
            else:
                helper, arguments = words[0], words[1:]

                if helper not in _BLOCK_HELPERS:
                    raise TemplateError(
                        f"{{{{#{helper}}}}}: the blocks are "
                        + ", ".join(sorted(_BLOCK_HELPERS))
                    )

            conditions.update(filter(None, map(_variable, arguments)))
            open_blocks.append(words[0] if inverse else helper)
            continue

        words = body.split()

        if len(words) != 1:
            raise TemplateError(
                f"{{{{{body}}}}}: a template places variables, it calls no helpers"
            )

        variable = _variable(words[0])

        if variable is not None:
            values.add(variable)

    if open_blocks:
        raise TemplateError(f"{{{{#{open_blocks[-1]}}}}} is never closed")

    return Placements(values=frozenset(values), conditions=frozenset(conditions))


def _variable(path: str) -> str | None:
    """
    The variable a path reads: its root, `case` for `case.x`. None for what a
    block has in scope rather than the template: `this`, `@index`, `../x`.
    """
    if path == "this" or path.startswith(("this.", "@", "../")):
        return None

    root = path.split(".", 1)[0]

    if not _IDENTIFIER.fullmatch(root):
        raise TemplateError(f"'{path}' is not a variable")

    return root
