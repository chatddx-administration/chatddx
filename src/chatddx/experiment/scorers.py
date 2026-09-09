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

`regex_match` grades against the row-ranked pattern language used by the
Expect files under `src/chatddx/data/expects` (see `_compile_row` for the
grammar).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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


# --- regex_match -------------------------------------------------------
#
# Each line of an Expect payload is one pattern, built out of:
#
#   word          a literal word, matched case-insensitively
#   a b           two (or more) words separated by a literal space are one
#                 phrase: the words must appear next to each other,
#                 separated by exactly one space -- "a b" matches "a b" but
#                 neither "a" nor "b" alone
#   x & y         AND: both x and y must match somewhere in the text
#   x | y         OR: either x or y must match
#   ( ... )       grouping, to override the default precedence
#
# Precedence, tightest to loosest: parentheses, then space (phrase), then
# `&`, then `|` -- so `a b | c` parses as `(a b) | c`, and
# `x & y | z & w` parses as `(x & y) | (z & w)`.


class _Node:
    def matches(self, text: str) -> bool:
        raise NotImplementedError


@dataclass
class _Phrase(_Node):
    pattern: re.Pattern[str]

    def matches(self, text: str) -> bool:
        return self.pattern.search(text) is not None


@dataclass
class _And(_Node):
    parts: list[_Node]

    def matches(self, text: str) -> bool:
        return all(part.matches(text) for part in self.parts)


@dataclass
class _Or(_Node):
    parts: list[_Node]

    def matches(self, text: str) -> bool:
        return any(part.matches(text) for part in self.parts)


_TOKEN_RE = re.compile(r"\(|\)|&|\||[^\s&|()]+")


class _RowParser:
    """Recursive-descent parser for one Expect row.

    expr   := or
    or     := and ('|' and)*
    and    := phrase ('&' phrase)*
    phrase := term+
    term   := WORD | '(' expr ')'
    """

    def __init__(self, tokens: list[str]):
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> str | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _advance(self) -> str | None:
        token = self._peek()
        self._pos += 1
        return token

    def parse(self) -> _Node:
        node = self._parse_or()
        if self._peek() is not None:
            raise ValueError(f"unexpected {self._peek()!r} in pattern")
        return node

    def _parse_or(self) -> _Node:
        parts = [self._parse_and()]
        while self._peek() == "|":
            self._advance()
            parts.append(self._parse_and())
        return parts[0] if len(parts) == 1 else _Or(parts)

    def _parse_and(self) -> _Node:
        parts = [self._parse_phrase()]
        while self._peek() == "&":
            self._advance()
            parts.append(self._parse_phrase())
        return parts[0] if len(parts) == 1 else _And(parts)

    def _parse_phrase(self) -> _Node:
        if self._peek() == "(":
            self._advance()
            node = self._parse_or()
            if self._advance() != ")":
                raise ValueError("unbalanced '(' in pattern")
            return node

        words: list[str] = []
        while self._peek() not in (None, "&", "|", "(", ")"):
            words.append(self._advance())  # type: ignore[arg-type]
        if not words:
            raise ValueError(f"expected a word, got {self._peek()!r}")

        literal = " ".join(words)
        return _Phrase(re.compile(re.escape(literal), re.IGNORECASE))


def _compile_row(row: str) -> _Node:
    tokens = _TOKEN_RE.findall(row)
    if not tokens:
        raise ValueError("empty pattern")
    return _RowParser(tokens).parse()


def row_matches(row: str, text: str) -> bool:
    """Whether `text` satisfies the pattern in `row` (see `_compile_row`)."""
    return _compile_row(row).matches(text)


def regex_match(run: RunModel) -> dict[str, Any]:
    """Score a Run's last assistant message against its Experiment's Expect
    payload, one pattern per line (see `_compile_row` for the grammar).

    Lines are tried in order starting at 1: the first line whose pattern
    matches wins, scoring `100 / line_number` (100 for the first line, 50
    for the second, and so on). Checking stops at the first match. If no
    line matches -- including when there's no assistant reply at all -- the
    score is 0. Blank lines are skipped (never match, but still count
    towards the line number of the lines after them).
    """
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

    score = 0.0
    matched_row: str | None = None

    if actual:
        for line_number, row in enumerate(expected.splitlines(), start=1):
            row = row.strip()
            if row and row_matches(row, actual):
                score = 100 / line_number
                matched_row = row
                break

    return {
        "score": score,
        "matched_row": matched_row,
        "expected": expected,
        "actual": actual,
    }
