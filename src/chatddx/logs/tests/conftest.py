from collections.abc import Callable
from typing import Any

import pytest
from rich.console import Console

from chatddx.dev.fake_vllm import FakeTransport
from chatddx.repl.commands import handle
from chatddx.repl.shell import Repl

type Run = Callable[..., None]


@pytest.fixture
def run_as(provision: Callable[..., None]) -> Callable[..., Run]:
    provisioned: set[str] = set()

    def run_as(identity: str, transport: Any = None) -> Run:
        if identity not in provisioned:
            provision(user=identity)
            provisioned.add(identity)

        repl = Repl(
            identity,
            Console(record=True, width=200),
            transport or FakeTransport(),
            seed=None,
        )

        def run(*lines: str) -> None:
            for line in lines:
                assert handle(repl, line)

        return run

    return run_as


@pytest.fixture
def run(run_as: Callable[..., Run]) -> Run:
    """alex's lines."""
    return run_as("alex")
