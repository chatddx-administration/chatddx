"""
A stack: a composition, and a variation of the stack slice. It replaces the
connection.

A stack is what answered a request: the machine, its operating system, the
LLM and the serving settings. For a NixOS container the OS is the
container's, and `host_os` is the host's, which holds the kernel and the
NVIDIA driver. A cloud stack has no OS and no serving: nothing below its
requests can be checked, and its machine says so.

The stack slice writes almost nothing into the request, only the `model`
field and where the request goes, and those are details: the endpoint and
the served name, the API and the name of the credential. Every other slice
is resolved against the stack (new-datamodel.md §2).
"""

from typing import Literal

from pydantic import Field, HttpUrl, model_validator

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.llm import (
    LLMFormDataIn,
    LLMTrailIn,
    LLMTrailOut,
)
from chatddx.repo.entities.machine import (
    MachineFormDataIn,
    MachineTrailIn,
    MachineTrailOut,
)
from chatddx.repo.entities.os import OsFormDataIn, OsTrailIn, OsTrailOut
from chatddx.repo.entities.serving import (
    ServingFormDataIn,
    ServingTrailIn,
    ServingTrailOut,
)
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

# The API a request is sent through: `vllm` for a stack of chatddx's own, and
# a cloud stack names its provider's.
type Api = Literal["vllm", "openai-chat", "openai-responses", "anthropic", "google"]


class StackDetails(Details):
    # where requests go
    endpoint: HttpUrl | None = None
    # the request's `model` field
    served_name: str | None = None
    api: Api | None = None
    # the name of a secret, never the secret
    credential: str | None = None


class StackTrailBase(BaseTrail):
    pass


class StackTrailIn(StackTrailBase, TrailIn):
    machine: MachineTrailIn
    os: OsTrailIn | None = None
    host_os: OsTrailIn | None = None
    llm: LLMTrailIn
    serving: ServingTrailIn | None = None

    @model_validator(mode="after")
    def _a_host_holds_a_container(self):
        if self.host_os is not None:
            if self.os is None:
                raise ValueError(
                    "a host OS is for a container: name the container's OS too"
                )

            if self.host_os.fingerprint == self.os.fingerprint:
                raise ValueError("a container's OS is not its host's")

        return self


class StackTrailRef(TrailRef, StackTrailBase):
    machine_id: int
    os_id: int | None
    host_os_id: int | None
    llm_id: int
    serving_id: int | None


class StackTrailOut(StackTrailBase, TrailOut):
    machine: MachineTrailOut
    os: OsTrailOut | None
    host_os: OsTrailOut | None
    llm: LLMTrailOut
    serving: ServingTrailOut | None


class StackBranchDetails(BranchDetails, StackDetails):
    pass


class StackBranchDetailsPatch(BranchDetailsPatch, StackDetails):
    pass


class StackBranchIn(BaseBranch[StackTrailIn], StackBranchDetails):
    pass


class StackBranchOut(BranchOut[StackTrailOut, StackDetails]):
    pass


class StackFormDataIn(StackTrailBase, BaseFormDataIn):
    machine: MachineFormDataIn
    os: OsFormDataIn | None = None
    host_os: OsFormDataIn | None = None
    llm: LLMFormDataIn
    serving: ServingFormDataIn | None = None

    endpoint: HttpUrl | None = None
    served_name: str | None = None
    api: Api | None = None
    credential: str | None = None


class StackFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    machine: CoercedStr
    os: CoercedStr | None
    host_os: CoercedStr | None
    llm: CoercedStr
    serving: CoercedStr | None

    endpoint: str | None
    served_name: str | None
    api: str | None
    credential: str | None
