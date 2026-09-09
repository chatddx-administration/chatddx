# src/chatddx/experiment/scorers.py
"""
Scorer functions: what `ExperimentModel.scorer` points to.

A scorer is any function importable by dotted path (Django's
`django.utils.module_loading.import_string` -- the same mechanism Django
itself uses for e.g. `MIDDLEWARE`) that takes a completed `RunModel` and
returns a JSON-serializable verdict. `chatddx.experiment.worker.score_run`
resolves an Experiment's `scorer`, calls it once per completed Run, and
stores whatever it returns, verbatim, on `Run.result`. A scorer may be a
regular function or a coroutine function -- `score_run` awaits either.

`exact_match` below is a reference implementation, usable as-is for
free-text Experiments: it grades a Run's final assistant reply against its
Experiment's Expect payload, verbatim.
"""

from __future__ import annotations

from typing import Any

from chatddx.core.choices import RoleChoices
from chatddx.experiment.models import RunModel
from chatddx.history.proxies import Message


def exact_match(run: RunModel) -> dict[str, Any]:
    """Score a Run by comparing its last assistant message, verbatim,
    against its Experiment's Expect payload."""
    message = (
        Message.objects.filter(
            session_id=run.session_id,
            role=RoleChoices.ASSISTANT,
        )
        .order_by("-pk")
        .first()
    )
    actual = message.content if message else None
    expected = run.experiment.expect.payload

    return {
        "correct": actual == expected,
        "expected": expected,
        "actual": actual,
    }
