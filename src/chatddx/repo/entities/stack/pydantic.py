from typing import Literal

from pydantic import HttpUrl, PositiveInt, model_validator

from chatddx.repo.entities.llm import (
    LLMTrailIn,
    LLMTrailOut,
)
from chatddx.repo.entities.machine import (
    MachineTrailIn,
    MachineTrailOut,
)
from chatddx.repo.entities.os import OsTrailIn, OsTrailOut
from chatddx.repo.entities.serving import (
    ServingTrailIn,
    ServingTrailOut,
)
from chatddx.repo.families import (
    BaseTrail,
    BranchDetails,
    BranchDetailsPatch,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
)

type Api = Literal["vllm", "openai-chat", "openai-responses", "anthropic", "google"]


class StackDetails(Details):
    endpoint: HttpUrl | None = None
    served_name: str | None = None
    api: Api | None = None
    credential: str | None = None
    max_jobs: PositiveInt = 1


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


class StackBranchOut(BranchOut[StackTrailOut, StackDetails]):
    pass
