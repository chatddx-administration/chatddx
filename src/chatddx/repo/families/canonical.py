"""
The canonical form a trail's fingerprint is taken of (data-generation.md §3.2).

It is the JSON Canonicalization Scheme (RFC 8785) with one exception: a value
whose order carries meaning keeps it. A JSON Schema is the case in point. A
constrained decoder emits keys in the order `properties` gives them, and a
model shown the schema reads every key in the order it is written. So each
object inside an order-carrying value is encoded as its ordered pairs before
canonicalizing, where the sort can't reach them.

A fingerprint names its scheme and version (`cddx-trail/1:sha256:…`), so a
change to any of this adds a version instead of silently breaking the
fingerprints already stored.
"""

import hashlib
import math
from collections.abc import Mapping
from typing import Any, cast

SCHEME = "cddx-trail/1"

# The one key of the object an ordered object is encoded as. Every object in
# an order-carrying value is wrapped, so a wrapped object can't be mistaken
# for a list of pairs that was written as one.
ORDERED_PAIRS = "ordered"

_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def ordered(value: Any) -> Any:
    """`value` with every object in it encoded as its ordered pairs."""
    match value:
        case Mapping():
            pairs = cast(Mapping[str, Any], value).items()
            return {ORDERED_PAIRS: [[key, ordered(item)] for key, item in pairs]}
        case list() | tuple():
            return [ordered(item) for item in cast(list[Any], value)]
        case _:
            return value


def canonical_json(value: Any) -> str:
    """`value` serialized as RFC 8785 prescribes."""
    match value:
        case None:
            return "null"
        case bool():
            return "true" if value else "false"
        case int() | float():
            return _number(value)
        case str():
            return _string(value)
        case Mapping():
            mapping = cast(Mapping[object, Any], value)
            keys = [key for key in mapping if isinstance(key, str)]

            if len(keys) != len(mapping):
                raise TypeError(f"an object's keys are strings: {value!r}")

            members = (
                f"{_string(key)}:{canonical_json(mapping[key])}"
                for key in sorted(keys, key=_utf16)
            )
            return "{" + ",".join(members) + "}"
        case list() | tuple():
            items = cast(list[Any], value)
            return "[" + ",".join(canonical_json(item) for item in items) + "]"
        case _:
            raise TypeError(f"{type(value).__name__} is not a JSON value: {value!r}")


def fingerprint(value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{SCHEME}:sha256:{digest}"


def fingerprint_digest(fingerprint: str) -> str:
    """The hex part of a fingerprint, whatever its scheme."""
    return fingerprint.rpartition(":")[2]


def _utf16(key: str) -> bytes:
    return key.encode("utf-16-be")


def _string(value: str) -> str:
    escaped = (
        _ESCAPES.get(char) or (f"\\u{ord(char):04x}" if ord(char) < 0x20 else char)
        for char in value
    )
    return '"' + "".join(escaped) + '"'


def _number(value: float) -> str:
    """A number as ECMAScript's Number.prototype.toString writes it."""
    if isinstance(value, int) and abs(value) <= 2**53:
        return str(value)

    number = float(value)

    if not math.isfinite(number):
        raise ValueError(f"{value!r} has no JSON form")

    if number == 0:
        return "0"

    sign = "-" if number < 0 else ""

    # repr gives the shortest digits that round-trip
    mantissa, _, exponent = repr(abs(number)).partition("e")
    whole, _, fraction = mantissa.partition(".")
    written = whole + fraction
    digits = written.lstrip("0")

    # where the decimal point sits, counted in `digits` from the left
    point = len(whole) - (len(written) - len(digits)) + int(exponent or 0)
    digits = digits.rstrip("0")

    if len(digits) <= point <= 21:
        text = digits + "0" * (point - len(digits))
    elif 0 < point <= 21:
        text = digits[:point] + "." + digits[point:]
    elif -6 < point <= 0:
        text = "0." + "0" * -point + digits
    else:
        exp = point - 1
        head = digits[0] + ("." + digits[1:] if len(digits) > 1 else "")
        text = f"{head}e{'+' if exp > 0 else '-'}{abs(exp)}"

    return sign + text
