from collections.abc import Callable
from typing import Any

import pytest
from rich.console import Console

from chatddx.repl.commands import handle
from chatddx.repl.shell import Repl
from chatddx.dev.fake_vllm import FakeTransport

type Say = Callable[..., str]


@pytest.fixture
def fake() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def repl(provision: Callable[..., None], fake: FakeTransport) -> Repl:
    """alex's repl on the test inventory, its trials sent to the fake vLLM."""
    provision()
    return Repl("alex", Console(record=True, width=200), transport=fake)


@pytest.fixture
def say(repl: Repl) -> Say:
    """Hand the repl its lines, and answer with what it wrote back."""
    return _say_to(repl)


@pytest.fixture
def say_through(provision: Callable[..., None]) -> Callable[[Any], Say]:
    """`say`, to a repl whose trials go through `transport`."""

    def say_through(transport: Any) -> Say:
        provision()
        return _say_to(Repl("alex", Console(record=True, width=200), transport))

    return say_through


def _say_to(repl: Repl) -> Say:
    def say(*lines: str) -> str:
        for line in lines:
            assert handle(repl, line)

        return repl.console.export_text()

    return say
