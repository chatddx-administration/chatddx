"""
Serving: the start-up settings of the server an LLM runs in.

vLLM only. The OS identity already pins them, since NixOS declares them, but
they are identified on their own too: the vLLM package, and the arguments
and environment variables that change what the LLM reads or the numbers
it computes (data-generation.md §1). The `--model` path is left out, since
that is the LLM's identity. What only changes speed is recorded as
description, for latency comparisons.

Arguments are held in canonical form: long option names without their
dashes, `_` spelled `-`, so two spellings of one argument are one argument.
"""

from collections.abc import Callable
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, JsonValue

from chatddx.core.fields import CoercedStr
from chatddx.repo.families import (
    BaseBranch,
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchDetails,
    BranchDetailsPatch,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
    TrailRef,
)
from chatddx.repo.families.fields import StorePath

# What a variation can need of the serving it is realized on. An LLM's
# facts name these as couplings, and resolution checks them against the
# serving's arguments (see `ServingTrailBase.provides`).
type Requirement = Literal["reasoning_parser", "tool_call_parser"]

# Arguments that change what the LLM reads or the numbers it computes: the
# first two kinds in data-generation.md §1. They belong to `args`.
OUTPUT_ARGS = frozenset(
    {
        "chat-template",
        "default-chat-template-kwargs",
        "generation-config",
        "override-generation-config",
        "reasoning-parser",
        "reasoning-config",
        "tool-call-parser",
        "enable-auto-tool-choice",
        "structured-outputs-config",
        "max-model-len",
        "seed",
        "logits-processors",
        "dtype",
        "quantization",
        "kv-cache-dtype",
        "tensor-parallel-size",
        "enforce-eager",
        "attention-backend",
        "speculative-config",
    }
)

# Arguments that only change speed. They belong to `performance`.
PERFORMANCE_ARGS = frozenset(
    {
        "gpu-memory-utilization",
        "max-num-seqs",
        "max-num-batched-tokens",
        "enable-prefix-caching",
        "host",
        "port",
    }
)

# Arguments held elsewhere, and where.
ELSEWHERE = {
    "model": "the --model path is the LLM's identity: it is llm.snapshot",
    "served-model-name": "the served name is the stack's served_name",
    "api-key": "an API key is a secret: a stack names it as its credential",
}


def canonical_args(
    where: Literal["args", "performance"],
) -> Callable[[dict[str, JsonValue]], dict[str, JsonValue]]:
    misplaced, belongs = {
        "args": (PERFORMANCE_ARGS, "only changes speed: it belongs to performance"),
        "performance": (OUTPUT_ARGS, "changes the output: it belongs to args"),
    }[where]

    def canonical(args: dict[str, JsonValue]) -> dict[str, JsonValue]:
        canonical_form: dict[str, JsonValue] = {}

        for key, value in args.items():
            name = key.lstrip("-").replace("_", "-")

            if name in canonical_form:
                raise ValueError(f"'{key}' is given twice")

            if name in ELSEWHERE:
                raise ValueError(f"'{key}': {ELSEWHERE[name]}")

            if name in misplaced:
                raise ValueError(f"'{key}' {belongs}")

            canonical_form[name] = value

        return dict(sorted(canonical_form.items()))

    return canonical


class ServingDetails(Details):
    performance: Annotated[
        dict[str, JsonValue],
        AfterValidator(canonical_args("performance")),
    ] = Field(default_factory=dict)


class ServingTrailBase(BaseTrail):
    # the vLLM package
    engine: StorePath
    args: Annotated[
        dict[str, JsonValue],
        AfterValidator(canonical_args("args")),
    ] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)

    def provides(self) -> frozenset[Requirement]:
        """The requirements a variation can have that this serving meets."""
        provided: set[Requirement] = set()

        if self.args.get("reasoning-parser"):
            provided.add("reasoning_parser")

        if self.args.get("tool-call-parser") and self.args.get(
            "enable-auto-tool-choice"
        ):
            provided.add("tool_call_parser")

        return frozenset(provided)


class ServingTrailIn(ServingTrailBase, TrailIn):
    pass


class ServingTrailRef(TrailRef, ServingTrailBase):
    pass


class ServingTrailOut(ServingTrailBase, TrailOut):
    pass


class ServingBranchDetails(BranchDetails, ServingDetails):
    pass


class ServingBranchDetailsPatch(BranchDetailsPatch, ServingDetails):
    pass


class ServingBranchIn(BaseBranch[ServingTrailIn], ServingBranchDetails):
    pass


class ServingBranchOut(BranchOut[ServingTrailOut, ServingDetails]):
    pass


class ServingFormDataIn(ServingTrailBase, BaseFormDataIn):
    performance: dict[str, JsonValue] = Field(default_factory=dict)


class ServingFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    engine: str
    args: dict[str, JsonValue]
    env: dict[str, str]
    performance: dict[str, JsonValue]
