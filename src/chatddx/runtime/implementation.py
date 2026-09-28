import hashlib
import importlib.abc
import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, override

TOOL_PACKAGE = "chatddx.runtime.tools"
SCORER_PACKAGE = "chatddx.scoring.scorers"


@dataclass(frozen=True)
class Implementation:
    entry_point: str
    function: Callable[..., Any]
    blob: str


def implementation(entry_point: str, package: str = TOOL_PACKAGE) -> Implementation:
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
    return hashlib.sha1(b"blob %d\0" % len(content) + content).hexdigest()


class _Source(importlib.abc.SourceLoader):
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
