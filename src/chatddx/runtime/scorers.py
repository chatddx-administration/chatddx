# src/chatddx/runtime/scorers.py
"""
How a run is judged.

A scorer trail carries a `command`, which names a function in this module the
same way a tool's command names one in `chatddx.runtime.tools`. The worker
resolves it with `resolve_scorer` and stores whatever the function returns on
`RunModel.result`, so a scorer's return value has to be JSON-serializable.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from chatddx.core.choices import RoleChoices
from chatddx.history.models import RunModel
from chatddx.history.proxies import Message

type Scorer = Callable[[RunModel], Any | Awaitable[Any]]


def last_reply(run: RunModel) -> str | None:
    """The agent's final answer in the session the run produced."""
    message = (
        Message.objects.filter(
            session_id=run.session_id,
            role=RoleChoices.ASSISTANT,
        )
        .order_by("-pk")
        .first()
    )

    return message.content if message else None


def exact_match(run: RunModel) -> dict[str, Any]:
    actual = last_reply(run)
    expected = run.experiment.expect.payload

    return {
        "correct": actual == expected,
        "expected": expected,
    }


class _Node:
    def matches(self, text: str) -> bool:
        raise NotImplementedError


@dataclass
class _Phrase(_Node):
    pattern: re.Pattern[str]

    @override
    def matches(self, text: str) -> bool:
        return self.pattern.search(text) is not None


@dataclass
class _And(_Node):
    parts: list[_Node]

    @override
    def matches(self, text: str) -> bool:
        return all(part.matches(text) for part in self.parts)


@dataclass
class _Or(_Node):
    parts: list[_Node]

    @override
    def matches(self, text: str) -> bool:
        return any(part.matches(text) for part in self.parts)


_TOKEN_RE = re.compile(r"\(|\)|&|\||[^\s&|()]+")


class _RowParser:
    def __init__(self, tokens: list[str]):
        self._tokens: list[str] = tokens
        self._pos: int = 0

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
            _ = self._advance()
            parts.append(self._parse_and())
        return parts[0] if len(parts) == 1 else _Or(parts)

    def _parse_and(self) -> _Node:
        parts = [self._parse_phrase()]
        while self._peek() == "&":
            _ = self._advance()
            parts.append(self._parse_phrase())
        return parts[0] if len(parts) == 1 else _And(parts)

    def _parse_phrase(self) -> _Node:
        if self._peek() == "(":
            _ = self._advance()
            node = self._parse_or()
            if self._advance() != ")":
                raise ValueError("unbalanced '(' in pattern")
            return node

        words: list[str] = []
        while self._peek() not in (None, "&", "|", "(", ")"):
            words.append(self._advance())  # pyright: ignore[reportArgumentType]
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
    """
    A row is a boolean expression over case-insensitive substrings, with `&`,
    `|` and parentheses -- `&` binds tighter than `|`, so
    `copd | exacerbation & pulmonary` reads as `copd | (exacerbation & pulmonary)`.
    """
    return _compile_row(row).matches(text)


def regex_match(run: RunModel) -> dict[str, Any]:
    """
    Score a reply against a ranked expectation: one row per acceptable answer,
    best first. The first row the reply satisfies decides the score, so hitting
    row 1 is worth 100, row 2 is worth 50, row n is worth 100/n.
    """
    actual = last_reply(run)
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
    }


# The commands a scorer trail may name. Kept explicit rather than reflected off
# the module, so that a stray helper in here can never be run as a scorer.
SCORERS: dict[str, Scorer] = {
    "exact_match": exact_match,
    "regex_match": regex_match,
}


def resolve_scorer(command: str) -> Scorer:
    """
    Look a scorer trail's command up among the scorers this module offers, the
    way `build_tools` looks a tool's command up in `chatddx.runtime.tools`.
    """
    try:
        return SCORERS[command]
    except KeyError as e:
        known = ", ".join(sorted(SCORERS)) or "none"
        raise LookupError(f"unknown scorer {command!r} (known: {known})") from e
