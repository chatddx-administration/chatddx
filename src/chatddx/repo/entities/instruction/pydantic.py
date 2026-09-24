"""
Instruction: a request-time slice (new-datamodel.md §2).

A variation is the templates of the system and user messages (Handlebars,
through pydantic-ai's `TemplateStr`) and the variables they declare: `case`,
and the slots other slices fill. An instruction never names an output: text
that asks for one output lives in that output's guidance, and reaches the
model through the `output_guidance` slot. So instruction and output can be
varied apart.

The case is a value, never a condition: a template places it and never
branches on it, so equal request skeletons mean equal requests for every
case (data-generation.md §3.1).
"""

from typing import Literal, get_args

from pydantic import Field, model_validator

from chatddx.core.fields import CoercedStr
from chatddx.repo.families import (
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchIn,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
    TrailRef,
)
from chatddx.repo.templates import placements

# `case`, and each slot by the slice that fills it: the output's guidance,
# the coercion's schema prompt and the toolset's guidance. A reasoning slot
# is left out until a study needs it (new-datamodel.md §8).
type Variable = Literal["case", "output_guidance", "schema_prompt", "tool_guidance"]

VARIABLES: tuple[Variable, ...] = get_args(Variable.__value__)


class InstructionTrailBase(BaseTrail):
    system: str = ""
    # `{{case}}` sends the case as it is, as chatddx always has
    user: str
    variables: list[Variable]

    @model_validator(mode="after")
    def _declared_is_placed(self):
        placed = placements(self.system) | placements(self.user)
        declared = set(self.variables)

        if len(declared) != len(self.variables):
            raise ValueError("a variable is declared twice")

        if "case" not in declared:
            raise ValueError("an instruction places the case: declare `case`")

        if "case" in placed.conditions:
            raise ValueError("the case is a value, never a condition")

        undeclared = sorted(placed.names - declared)

        if undeclared:
            raise ValueError(f"{undeclared} placed but not declared")

        unplaced = sorted(declared - placed.values)

        if unplaced:
            raise ValueError(f"{unplaced} declared but never placed")

        # one order for one set, so the same declaration is the same content
        self.variables = sorted(self.variables, key=VARIABLES.index)

        return self


class InstructionTrailIn(InstructionTrailBase, TrailIn):
    pass


class InstructionTrailRef(TrailRef, InstructionTrailBase):
    pass


class InstructionTrailOut(InstructionTrailBase, TrailOut):
    pass


class InstructionBranchIn(BranchIn[InstructionTrailIn]):
    pass


class InstructionBranchOut(BranchOut[InstructionTrailOut, Details]):
    pass


class InstructionFormDataIn(InstructionTrailBase, BaseFormDataIn):
    pass


class InstructionFormDataOut(InstructionTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
