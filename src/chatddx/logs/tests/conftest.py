from collections.abc import Callable
from typing import Any

import pytest

from chatddx.conftest import Provision, SayAs

type Run = Callable[..., None]


@pytest.fixture
def run_as(provision: Provision, say_as: SayAs) -> Callable[..., Run]:
    # alex's is seeded for the session
    provisioned: set[str] = {"alex"}

    def run_as(identity: str, transport: Any = None) -> Run:
        if identity not in provisioned:
            _ = provision(user=identity)
            provisioned.add(identity)

        say = say_as(identity, transport)

        def run(*lines: str) -> None:
            _ = say(*lines)

        return run

    return run_as


@pytest.fixture
def run(run_as: Callable[..., Run]) -> Run:
    """alex's lines."""
    return run_as("alex")
