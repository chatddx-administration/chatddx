"""
What runs when a model calls a tool, or a scorer scores a run: a function in
one of chatddx's own files, in `chatddx.runtime.tools` or
`chatddx.scoring.scorers`, named by an entry point (`module.path:function`).
Nothing else runs, whoever's branch names it.

A file is loaded afresh from its bytes each time, and those bytes' git blob
id is kept beside what they define: what ran is what the id names, even
after an edit in a long-running process, and `git cat-file blob <id>` gets
it back.
"""

import hashlib
import importlib.abc
import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, override

TOOLS = "chatddx.runtime.tools"
SCORERS = "chatddx.scoring.scorers"


@dataclass(frozen=True)
class Implementation:
    entry_point: str
    function: Callable[..., Any]
    blob: str


def implementation(entry_point: str, package: str = TOOLS) -> Implementation:
    """The function `entry_point` names in `package`, and its file's blob id."""
    module_name, _, name = entry_point.partition(":")

    if not module_name.startswith(f"{package}."):
        raise ValueError(f"{entry_point} isn't one of chatddx's own, in {package}")

    try:
        spec = importlib.util.find_spec(module_name)
    except ModuleNotFoundError:
        spec = None

    if spec is None or spec.origin is None:
        raise ValueError(f"there is no {module_name}")

    source = Path(spec.origin).read_bytes()
    function = getattr(_load(module_name, spec.origin, source), name, None)

    if function is None:
        raise ValueError(f"there is no {entry_point}")

    return Implementation(entry_point, function, blob_of(source))


def blob_of(content: bytes) -> str:
    """Git's id for a file's content, as `git hash-object` makes it."""
    return hashlib.sha1(b"blob %d\0" % len(content) + content).hexdigest()


class _Source(importlib.abc.SourceLoader):
    """A module's source, as bytes already read: nothing is read again."""

    def __init__(self, origin: str, source: bytes):
        self.origin: str = origin
        self.source: bytes = source

    @override
    def get_filename(self, fullname: str) -> str:
        return self.origin

    @override
    def get_data(self, path: str) -> bytes:
        return self.source


def _load(name: str, origin: str, source: bytes) -> ModuleType:
    loader = _Source(origin, source)
    spec = importlib.util.spec_from_loader(name, loader, origin=origin)
    assert spec is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)

    return module
