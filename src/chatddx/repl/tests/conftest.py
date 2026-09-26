import pytest
from rich.console import Console

from chatddx.conftest import Say, say_to
from chatddx.dev.fake_vllm import FakeTransport
from chatddx.repl.shell import Repl


@pytest.fixture
def repl(fake: FakeTransport) -> Repl:
    return Repl("alice", Console(record=True, width=200), transport=fake, seed=None)


@pytest.fixture
def say(repl: Repl) -> Say:
    return say_to(repl)
