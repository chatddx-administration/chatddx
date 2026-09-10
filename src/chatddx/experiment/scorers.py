# src/chatddx/experiment/scorers.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from chatddx.core.choices import RoleChoices
from chatddx.experiment.models import RunModel
from chatddx.history.proxies import Message


def exact_match(run: RunModel) -> dict[str, Any]:
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

    # The actual reply isn't duplicated here -- it's already on the Run's
    # session (see RunModel.session).
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
    return _compile_row(row).matches(text)


def regex_match(run: RunModel) -> dict[str, Any]:
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

    # The actual reply isn't duplicated here -- it's already on the Run's
    # session (see RunModel.session).
    return {
        "score": score,
        "matched_row": matched_row,
        "expected": expected,
    }
