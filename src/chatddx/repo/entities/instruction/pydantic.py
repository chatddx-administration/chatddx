"""
What an agent is told to do, as a bundle of its own.

The text used to sit on the agent as its one primitive field. It is a
bundle now, so an agent is nothing but the things it points at, and the
same instruction can be pointed at twice.

A bundle of one field is still carried flat wherever a person meets it --
a textarea on the agent forms, `instructions = "..."` in an inventory --
so `as_definition` and `definition_text` are the two directions between
the text and the bundle it stands for.
"""

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.families import (
    BranchSchema,
    BranchSpec,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)
from chatddx.repo.families.pydantic import BaseFormDataIn, BaseFormDataOut, BaseTrail


def as_definition(v: Any) -> Any:
    """
    The bundle a bare string stands for.

    Whatever hands over an instruction as text -- a form field, an
    inventory record that named it inline -- says the same thing as a
    bundle with that text as its definition.
    """
    match v:
        case str():
            return {"definition": v}
        case _:
            return v


def definition_text(v: Any) -> Any:
    """
    The text of an instruction, from the bundle or from the text itself.

    The other direction of `as_definition`: what a flat form puts in its
    one field, whether it is handed the bundle or the text.
    """
    match v:
        case {"definition": definition}:
            return definition
        case BaseModel():
            return v.definition  # pyright: ignore[reportAttributeAccessIssue]
        case _:
            return v


# An instruction where the text is what is carried: the agent forms and the
# template registry they read from.
DefinitionText = Annotated[str, BeforeValidator(definition_text)]


class InstructionTrailBase(BaseTrail):
    definition: str


class InstructionTrailSchema(InstructionTrailBase, TrailSchema):
    pass


class InstructionTrailSchemaRef(
    TrailSchemaRef,
    InstructionTrailBase,
):
    pass


class InstructionTrailSpec(InstructionTrailBase, TrailSpec):
    pass


class InstructionBranchSchema(BranchSchema[InstructionTrailSchema]):
    pass


class InstructionBranchSpec(BranchSpec[InstructionTrailSpec]):
    pass


class InstructionFormDataIn(InstructionTrailBase, BaseFormDataIn):
    pass


class InstructionFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    definition: str
