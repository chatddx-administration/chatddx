"""
A stack: a composition, and a variation of the model slice. It replaces the
connection.

A stack is what answered a request: the machine, its operating system, the
model and the serving settings. For a NixOS container the OS is the
container's, and `host_os` is the host's, which holds the kernel and the
NVIDIA driver. A cloud stack has no OS and no serving: nothing below its
requests can be checked, and its machine says so.

The model slice writes almost nothing into the request, only the `model`
field and where the request goes, and those are details: the endpoint and
the served name, the API and the name of the credential. Every other slice
is resolved against the stack (new-datamodel.md §2).
"""

from typing import Literal

from pydantic import Field, HttpUrl, model_validator

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.machine import (
    MachineFormDataIn,
    MachineTrailSchema,
    MachineTrailSpec,
)
from chatddx.repo.entities.model import (
    ModelFormDataIn,
    ModelTrailSchema,
    ModelTrailSpec,
)
from chatddx.repo.entities.os import OsFormDataIn, OsTrailSchema, OsTrailSpec
from chatddx.repo.entities.serving import (
    ServingFormDataIn,
    ServingTrailSchema,
    ServingTrailSpec,
)
from chatddx.repo.families import (
    BaseBranch,
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchDetailsPatch,
    BranchSchemaDetails,
    BranchSpec,
    Details,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
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


class StackTrailSchema(StackTrailBase, TrailSchema):
    machine: MachineTrailSchema
    os: OsTrailSchema | None = None
    host_os: OsTrailSchema | None = None
    model: ModelTrailSchema
    serving: ServingTrailSchema | None = None

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


class StackTrailSchemaRef(TrailSchemaRef, StackTrailBase):
    machine_id: int
    os_id: int | None
    host_os_id: int | None
    model_id: int
    serving_id: int | None


class StackTrailSpec(StackTrailBase, TrailSpec):
    machine: MachineTrailSpec
    os: OsTrailSpec | None
    host_os: OsTrailSpec | None
    model: ModelTrailSpec
    serving: ServingTrailSpec | None


class StackBranchDetails(BranchSchemaDetails, StackDetails):
    pass


class StackBranchDetailsPatch(BranchDetailsPatch, StackDetails):
    pass


class StackBranchSchema(BaseBranch[StackTrailSchema], StackBranchDetails):
    pass


class StackBranchSpec(BranchSpec[StackTrailSpec, StackDetails]):
    pass


class StackFormDataIn(StackTrailBase, BaseFormDataIn):
    machine: MachineFormDataIn
    os: OsFormDataIn | None = None
    host_os: OsFormDataIn | None = None
    model: ModelFormDataIn
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
    model: CoercedStr
    serving: CoercedStr | None

    endpoint: str | None
    served_name: str | None
    api: str | None
    credential: str | None
