"""
Patterns an answer is held to, and the scorers that hold it to them.

A pattern names words, whole and in any case: `pneumonia` isn't found in
"pneumonias", nor `mi` in "anemia". A trailing `*` takes any word that
starts so (`meningit*`), and words side by side are a phrase, found side by
side (`acute coronary syndrome`). `&` needs both sides, `|` either, `&` binds
tighter than `|`, and parentheses group: `(renal | kidney) & stone*`. A
pattern is held to one item at a time, a diagnosis, a sentence or a field,
never to two at once.

A scorer takes what a view read, or None where the run came to no answer,
and a target pattern, and says what it makes of them. This file imports
nothing else of chatddx's, so its git blob id names every scorer in it.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import NamedTuple

_TOKEN = re.compile(r"\(|\)|&|\||[^\s&|()]+")
_WORD = re.compile(r"\w+")
_BREAK = re.compile(r"\n+|(?<=[.!?])\s+")


class Scored(NamedTuple):
    value: float | None
    answer: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class _Term:
    word: str
    stem: bool

    def fits(self, word: str) -> bool:
        return word.startswith(self.word) if self.stem else word == self.word


@dataclass(frozen=True)
class _Phrase:
    terms: tuple[_Term, ...]

    def find(self, words: list[str]) -> int | None:
        span = len(self.terms)

        for at in range(len(words) - span + 1):
            if all(term.fits(words[at + i]) for i, term in enumerate(self.terms)):
                return at

        return None


@dataclass(frozen=True)
class _All:
    parts: tuple["_Phrase | _All | _Any", ...]

    def find(self, words: list[str]) -> int | None:
        found = [part.find(words) for part in self.parts]
        return None if None in found else min(i for i in found if i is not None)


@dataclass(frozen=True)
class _Any:
    parts: tuple["_Phrase | _All | _Any", ...]

    def find(self, words: list[str]) -> int | None:
        found = [i for part in self.parts if (i := part.find(words)) is not None]
        return min(found) if found else None


class Pattern:
    def __init__(self, text: str):
        self.text: str = text
        self._tokens: list[str] = _TOKEN.findall(text)
        self._at: int = 0

        if not self._tokens:
            raise ValueError("a pattern names at least one word")

        self._root: _Phrase | _All | _Any = self._any()

        if self._peek() is not None:
            raise ValueError(f"unexpected {self._peek()!r} in {text!r}")

    def find(self, text: str) -> int | None:
        """Where in `text` the pattern is first found, by the characters before it."""
        spans = list(_WORD.finditer(text))
        at = self._root.find([span.group().casefold() for span in spans])

        return None if at is None else spans[at].start()

    def _peek(self) -> str | None:
        return self._tokens[self._at] if self._at < len(self._tokens) else None

    def _take(self) -> str | None:
        token = self._peek()
        self._at += 1
        return token

    def _any(self) -> "_Phrase | _All | _Any":
        parts = [self._all()]

        while self._peek() == "|":
            _ = self._take()
            parts.append(self._all())

        return parts[0] if len(parts) == 1 else _Any(tuple(parts))

    def _all(self) -> "_Phrase | _All | _Any":
        parts = [self._one()]

        while self._peek() == "&":
            _ = self._take()
            parts.append(self._one())

        return parts[0] if len(parts) == 1 else _All(tuple(parts))

    def _one(self) -> "_Phrase | _All | _Any":
        if self._peek() == "(":
            _ = self._take()
            inner = self._any()

            if self._take() != ")":
                raise ValueError(f"a '(' in {self.text!r} is never closed")

            return inner

        terms: list[_Term] = []

        while (token := self._peek()) not in (None, "&", "|", "(", ")"):
            _ = self._take()
            terms += _terms(token)

        if not terms:
            raise ValueError(f"a word is missing in {self.text!r}")

        return _Phrase(tuple(terms))


def _terms(token: str) -> list[_Term]:
    stem = token.endswith("*")
    words = [word.casefold() for word in _WORD.findall(token)]

    if not words:
        raise ValueError(f"{token!r} names no word")

    return [_Term(word, stem and i == len(words) - 1) for i, word in enumerate(words)]


def _units(text: str) -> Iterator[tuple[int, str]]:
    """Each sentence or line of `text`, and the characters before it."""
    start = 0

    for gap in _BREAK.finditer(text):
        yield start, text[start : gap.start()]
        start = gap.end()

    yield start, text[start:]


def reciprocal_rank(items: list[str] | None, target: str) -> Scored:
    """1/rank of the first item the target is found in, and 0 where it isn't."""
    if items is None:
        return Scored(0.0, reason="no answer")

    pattern = Pattern(target)

    for rank, item in enumerate(items, 1):
        if pattern.find(item) is not None:
            return Scored(1 / rank, answer=f"{rank}. {item}")

    return Scored(0.0, reason="not listed")


def first_mention(items: list[str] | None, target: str) -> Scored:
    """
    The characters before the target is first named in the text: in the
    first sentence or line it is found in, at its first word.
    """
    if items is None:
        return Scored(None, reason="no answer")

    pattern = Pattern(target)

    for item in items:
        for start, unit in _units(item):
            at = pattern.find(unit)

            if at is not None:
                return Scored(float(start + at), answer=unit.strip())

    return Scored(None, reason="never named")


def mentions(items: list[str] | None, target: str) -> Scored:
    """1 where the target is found in what the view read, and 0 where it isn't."""
    if items is None:
        return Scored(0.0, reason="no answer")

    pattern = Pattern(target)

    for item in items:
        if pattern.find(item) is not None:
            return Scored(1.0, answer=item)

    return Scored(0.0, reason="not named")
