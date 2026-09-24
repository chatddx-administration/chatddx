"""
The client a trial runs on: the chatddx build that turns a configuration into
a request (new-datamodel.md §6). A build is its store path; a dev shell has
none, and says which revision it runs at instead, with "-dirty" when the
checkout has changes. Either way the versions of the libraries that build
requests are what they are where it runs.
"""

import re
import subprocess
from dataclasses import dataclass, field
from functools import cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import chatddx
from chatddx.repo.entities.client.pydantic import ClientTrailSchema

PACKAGES = ("pydantic-ai-slim", "openai", "inspect-ai")

STORE_PATH = re.compile(r"^/nix/store/[0-9a-z]{32}-[^/]+")


@dataclass(frozen=True)
class Client:
    build: str | None
    rev: str | None
    packages: dict[str, str] = field(default_factory=dict[str, str])

    @property
    def trail(self) -> ClientTrailSchema:
        return ClientTrailSchema(build=self.build)


@cache
def running() -> Client:
    here = Path(chatddx.__file__).resolve()
    build = build_of(here)

    return Client(
        build=build,
        rev=None if build else rev_of(here.parent),
        packages=versions(PACKAGES),
    )


def build_of(path: Path) -> str | None:
    """The store path `path` is in, if it is in one."""
    found = STORE_PATH.match(str(path))
    return found.group(0) if found else None


def rev_of(checkout: Path) -> str | None:
    def git(*args: str) -> str | None:
        try:
            done = subprocess.run(
                ["git", *args],
                cwd=checkout,
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None

        return done.stdout.strip()

    rev = git("rev-parse", "HEAD")

    if rev is None:
        return None

    return f"{rev}-dirty" if git("status", "--porcelain") else rev


def versions(packages: tuple[str, ...]) -> dict[str, str]:
    found: dict[str, str] = {}

    for package in packages:
        try:
            found[package] = version(package)
        except PackageNotFoundError:
            continue

    return found
