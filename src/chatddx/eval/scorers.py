"""
How a run's output is judged against an expectation.

A scorer is code, named by the `command` its trail carries, and it reads one
thing: the output the run recorded (`RunModel.output`) -- the value the agent
returned, whatever its output type's coercion strategy made the model send
over the wire. It never reads the transcript, which differs by coercion
strategy: a structured reply delivered as a tool call has no text at all.

What a scorer can read is a fact about its code, so it is registered with
it: `accepts` is the JSON Schema of the outputs it can judge. That is what
says whether it can judge an output type at all (`Scorer.reads`), before
anything runs, and what an output is checked against before it is judged
(`Scorer.check`), after.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, override

import jsonschema
from pydantic import JsonValue

from chatddx.core.json_schema import satisfies
from chatddx.repo.entities.output_type.pydantic import TEXT_SCHEMA, output_schema

type Judge = Callable[[Any, str], Any | Awaitable[Any]]

LIST_OF_TEXT: dict[str, JsonValue] = {
    "type": "array",
    "items": TEXT_SCHEMA,
}


class UnreadableOutputError(ValueError):
    pass


@dataclass(frozen=True)
class Scorer:
    command: str
    # (output, expectation payload) -> result
    judge: Judge
    # every output `judge` is handed is valid against this
    accepts: dict[str, JsonValue]

    def reads(self, definition: Mapping[str, Any]) -> bool:
        """
        Whether every output a run can return under an output type with this
        `definition` is one this scorer can judge.
        """
        return satisfies(output_schema(definition), self.accepts)

    def check(self, output: Any) -> None:
        try:
            jsonschema.validate(instance=output, schema=self.accepts)
        except jsonschema.ValidationError as e:
            raise UnreadableOutputError(
                f"{self.command} cannot judge this output: {e.message}"
            ) from e


def exact_match(output: str, expected: str) -> dict[str, Any]:
    return {
        "correct": output == expected,
        "expected": expected,
    }


def reciprocal_rank(output: list[str], expected: str) -> dict[str, Any]:
    """
    Score a ranked list against the answer it should contain: the first item
    that satisfies the expectation's pattern decides the score, so an answer
    in first place is worth 100, in second 50, in n-th 100/n, and missing
    from the list 0.
    """
    pattern = compile_pattern(expected)

    for rank, item in enumerate(output, start=1):
        if pattern.matches(item):
            return {
                "score": 100 / rank,
                "rank": rank,
                "matched": item,
                "expected": expected,
            }

    return {
        "score": 0.0,
        "rank": None,
        "matched": None,
        "expected": expected,
    }


class _Node:
    def matches(self, text: str) -> bool:
        _ = text
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


class _PatternParser:
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


def compile_pattern(pattern: str) -> _Node:
    """
    A pattern is a boolean expression over case-insensitive substrings, with
    `&`, `|` and parentheses -- `&` binds tighter than `|`, so
    `copd | exacerbation & pulmonary` reads as `copd | (exacerbation & pulmonary)`.

    It is one line. An expectation used to be several, one acceptable answer
    per row, best first; the ranking is the output's to give now, and a
    second line would otherwise be read as more words of the first phrase.
    """
    if len([line for line in pattern.splitlines() if line.strip()]) > 1:
        raise ValueError(
            "a pattern is a single line: join alternative answers with '|'"
        )

    tokens = _TOKEN_RE.findall(pattern)
    if not tokens:
        raise ValueError("empty pattern")
    return _PatternParser(tokens).parse()


def pattern_matches(pattern: str, text: str) -> bool:
    return compile_pattern(pattern).matches(text)


SCORERS: dict[str, Scorer] = {
    scorer.command: scorer
    for scorer in (
        Scorer("exact_match", exact_match, accepts=TEXT_SCHEMA),
        Scorer("reciprocal_rank", reciprocal_rank, accepts=LIST_OF_TEXT),
    )
}


def resolve_scorer(command: str) -> Scorer:
    try:
        return SCORERS[command]
    except KeyError as e:
        known = ", ".join(sorted(SCORERS)) or "none"
        raise LookupError(f"unknown scorer {command!r} (known: {known})") from e


def scorer_reads(command: str, definition: Mapping[str, Any]) -> bool | None:
    """
    Whether the scorer a trail names can judge the output of an output type
    with this `definition`: None where the command names no scorer this code
    has, since then nothing says what it reads.
    """
    scorer = SCORERS.get(command)

    return None if scorer is None else scorer.reads(definition)
