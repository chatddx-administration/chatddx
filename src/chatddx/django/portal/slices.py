# pyright: basic
"""
A slice's variation as the portal's pages say it: what each slice and each
of its fields is called; its fields, a line each; and what one variation
does in place of another, field by field.
"""

import json
from typing import Any

from django.utils.translation import gettext, gettext_lazy as _

from chatddx.django.portal.records import Change, Field, or_none, said
from chatddx.repo.entities.output.pydantic import VIEWS
from chatddx.repo.entity_names import EntityName

# what the page calls each slice
LABELS: dict[str, Any] = {
    "instruction": _("Instruction"),
    "output": _("Output"),
    "coercion": _("Coercion"),
    "reasoning": _("Reasoning"),
    "sampling": _("Sampling"),
    "toolset": _("Toolset"),
}

# what the page calls each of a slice's fields, in the order it shows them
FIELDS: dict[str, dict[str, Any]] = {
    "instruction": {
        "system": _("System"),
        "user": _("User"),
        "variables": _("Variables"),
    },
    "output": {
        "guidance": _("Guidance"),
        "views": _("Views"),
        "answer_schema": _("Answer schema"),
    },
    "coercion": {
        "mode": _("Mode"),
        "schema_prompt": _("Schema prompt"),
        "tool_description": _("Tool description"),
    },
    "reasoning": {
        "effort": _("Effort"),
        "budget": _("Budget"),
    },
    "sampling": {
        "defaults": _("Defaults"),
        "temperature": _("Temperature"),
        "top_p": _("Top p"),
        "top_k": _("Top k"),
        "max_tokens": _("Max tokens"),
        "presence_penalty": _("Presence penalty"),
        "frequency_penalty": _("Frequency penalty"),
        "stop": _("Stop"),
    },
    "toolset": {
        "tools": _("Tools"),
        "guidance": _("Guidance"),
    },
}

# what a sampling's defaults are, in words
DEFAULTS: dict[str, Any] = {
    "recommended": _("what the LLM's facts recommend for the reasoning it comes to"),
    "generation_config": _("the LLM's generation config, as its server has it"),
}

# a change of a text too long for a line: its start, and that there is more
BRIEF = 60


def values_of(entity: EntityName, trail: Any) -> dict[str, Any]:
    """A slice's fields, as the page compares them: a toolset's tools by name."""
    if trail is None:
        return {name: None for name in FIELDS[entity]}

    values = {name: getattr(trail, name, None) for name in FIELDS[entity]}

    if entity == "toolset":
        values["tools"] = [tool.name for tool in trail.tools]

    return values


def done(entity: EntityName, own: Any, set_: Any) -> list[Change]:
    """What a variation set does in place of the configuration's own: each field it changes."""
    before, after = values_of(entity, own), values_of(entity, set_)

    if entity == "toolset" and (own is None or set_ is None):
        return [
            Change(
                FIELDS[entity]["tools"],
                brief(before["tools"]) if own else gettext("none"),
                brief(after["tools"]) if set_ else gettext("none"),
            )
        ]

    # a schema takes more than a line to say: that it changed
    return [
        Change(label)
        if name == "answer_schema" and before[name] and after[name]
        else Change(label, brief(before[name]), brief(after[name]))
        for name, label in FIELDS[entity].items()
        if before[name] != after[name]
    ]


def brief(value: Any) -> str:
    """A value in a line: a text by its start, where it is longer than one."""
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return ", ".join(value) or gettext("none")

    if isinstance(value, dict) and "type" in value:
        return gettext("a schema")

    if isinstance(value, str):
        line = " ".join(value.split())

        if not line:
            return gettext("nothing")

        return (
            line
            if len(line) <= BRIEF and "\n" not in value.strip()
            else f"“{line[: BRIEF - 1]}…”"
        )

    return said(value)


def fields_of(entity: EntityName, trail: Any) -> list[Field]:
    labels = FIELDS[entity]

    match entity:
        case "instruction":
            return [
                Field(labels["system"], or_none(trail.system), text=True),
                Field(labels["user"], or_none(trail.user), text=True),
                Field(labels["variables"], items=list(trail.variables)),
            ]
        case "output":
            schema = trail.answer_schema

            return [
                Field(labels["guidance"], or_none(trail.guidance), text=True),
                Field(
                    labels["views"],
                    # in the order the outputs' views go, which the database doesn't keep
                    items=[
                        f"{view}: {trail.views[view]}"
                        for view in VIEWS
                        if view in trail.views
                    ],
                ),
                Field(
                    labels["answer_schema"],
                    gettext("none: the answer is free text")
                    if schema is None
                    else json.dumps(schema, indent=2, ensure_ascii=False),
                    folded=schema is not None,
                ),
            ]
        case "coercion":
            return [
                Field(labels["mode"], trail.mode),
                Field(labels["schema_prompt"], or_none(trail.schema_prompt), text=True),
                Field(
                    labels["tool_description"],
                    or_none(trail.tool_description),
                    text=True,
                ),
            ]
        case "reasoning":
            return [
                Field(labels["effort"], trail.effort),
                Field(
                    labels["budget"],
                    "—"
                    if trail.budget is None
                    else gettext("%(tokens)d thinking tokens")
                    % {"tokens": trail.budget},
                ),
            ]
        case "sampling":
            return [
                Field(
                    labels["defaults"], f"{trail.defaults}: {DEFAULTS[trail.defaults]}"
                ),
                *(
                    Field(label, said(getattr(trail, name)))
                    for name, label in labels.items()
                    if name != "defaults" and getattr(trail, name) is not None
                ),
            ]
        case _ if trail is None:
            return [Field(labels["tools"], gettext("none: no tool is offered"))]
        case _:
            return [
                Field(
                    labels["tools"],
                    items=[
                        f"{tool.name}: {tool.description}"
                        if tool.description
                        else tool.name
                        for tool in trail.tools
                    ],
                ),
                Field(labels["guidance"], or_none(trail.guidance), text=True),
            ]
