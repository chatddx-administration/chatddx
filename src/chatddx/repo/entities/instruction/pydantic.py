from typing import Literal, get_args

from pydantic import model_validator

from chatddx.repo.families import (
    BaseTrail,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
)
from chatddx.repo.templates import placements

type Variable = Literal["case", "output_guidance", "schema_prompt", "tool_guidance"]

VARIABLES: tuple[Variable, ...] = get_args(Variable.__value__)


class InstructionTrailBase(BaseTrail):
    system: str = ""
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

        self.variables = sorted(self.variables, key=VARIABLES.index)

        return self


class InstructionTrailIn(InstructionTrailBase, TrailIn):
    pass


class InstructionTrailOut(InstructionTrailBase, TrailOut):
    pass


class InstructionBranchOut(BranchOut[InstructionTrailOut, Details]):
    pass
