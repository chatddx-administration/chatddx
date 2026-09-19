from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from typer.testing import CliRunner

from chatddx import manage
from chatddx.core import worker

runner = CliRunner()


def record_call(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    calls: list[str],
) -> None:
    async def _recorded() -> None:
        calls.append(name)

    fn: Callable[[], Coroutine[Any, Any, None]] = _recorded
    monkeypatch.setattr(worker, name, fn)


def test_worker_is_a_command_group_of_its_own():
    result = runner.invoke(manage.app, ["--help"])

    assert result.exit_code == 0
    assert "worker" in result.stdout


def test_worker_run_drains_the_queue_once(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []
    record_call(monkeypatch, "drain", calls)

    result = runner.invoke(manage.app, ["worker", "run"])

    assert result.exit_code == 0, result.output
    assert calls == ["drain"]


def test_worker_serve_keeps_processing(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []
    record_call(monkeypatch, "serve", calls)

    result = runner.invoke(manage.app, ["worker", "serve"])

    assert result.exit_code == 0, result.output
    assert calls == ["serve"]
