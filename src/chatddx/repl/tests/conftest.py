from collections.abc import Callable
from typing import Any

import pytest
from rich.console import Console

from chatddx.dev.fake_vllm import FakeTransport
from chatddx.repl.commands import handle
from chatddx.repl.shell import Repl

type Say = Callable[..., str]


@pytest.fixture
def fake() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def repl(fake: FakeTransport) -> Repl:
    return Repl("alex", Console(record=True, width=200), transport=fake, seed=None)


@pytest.fixture
def say(repl: Repl) -> Say:
    return _say_to(repl)


@pytest.fixture
def say_through() -> Callable[[Any], Say]:
    def say_through(transport: Any) -> Say:
        return _say_to(
            Repl("alex", Console(record=True, width=200), transport, seed=None)
        )

    return say_through


def _say_to(repl: Repl) -> Say:
    def say(*lines: str) -> str:
        for line in lines:
            assert handle(repl, line)

        return repl.console.export_text()

    return say
