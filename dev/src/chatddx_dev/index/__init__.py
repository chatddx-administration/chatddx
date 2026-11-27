import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from babel.messages.catalog import Catalog

from chatddx import locale
from chatddx.markers import stamped, stamps
from chatddx_dev import project

from . import anchored, bash, frontend, surfaces
from .code import Code
from .facts import Entry, Facts, dumped
from .trace import Trace

__all__ = [
    "CATALOG",
    "COMMENTS",
    "KINDS",
    "SURFACES",
    "WHOOPSES",
    "Proof",
    "check",
    "facts",
    "proofs",
    "write",
]

PARTS = project.PROJECT_ROOT / "docs" / "parts"
_FRONTEND = ("frontend/src/lib", "frontend/src/islands")
CATALOG = project.PROJECT_ROOT / "docs" / "catalog"
SURFACES = project.PROJECT_ROOT / "docs" / "surfaces"
COMMENTS = project.PROJECT_ROOT / "docs" / "comments"
WHOOPSES = project.PROJECT_ROOT / "docs" / "whoopses"
KINDS = ("catalog", "comments", "surfaces", "whoopses")
_FINDING = "chatddx.factors.base.Finding"
_WHOOPS = "chatddx.whoops.Whoops"


@dataclass(frozen=True)
class Proof:
    path: Path
    current: str | None
    written: str

    @property
    def behind(self) -> bool:
        return self.current != self.written

    @property
    def pending(self) -> int:
        return 0 if self.current is None else len(stamps(self.current))

    @property
    def new(self) -> int:
        held = Counter(stamps(self.current or ""))
        return (Counter(stamps(self.written)) - held).total()


def proofs(
    parts: Iterable[str] | None = None, kinds: Iterable[str] | None = None
) -> list[Proof]:
    """The surface, the comment index, the whoops index and the catalog of each part, or
    each part named, or those of the kinds named, at a stage from which each is stamped,
    whatever the language of its code: its Python modules' public names and the
    frontend's exports and props; its comments in what Python, SQL, TOML, bash, bats,
    TypeScript or Svelte is in it; its claims in its Python, and the messages it says,
    its tests left out. Griffe reads each package once, shfmt each script once, node a
    part's frontend once, and the locale's extraction the whole code once."""
    root = project.PROJECT_ROOT
    codes: dict[Path, Code] = {}
    traces: dict[Path, Trace] = {}
    said: list[Catalog] = []
    found: list[Proof] = []
    for name in sorted(project.PARTS if parts is None else parts):
        part = project.PARTS.get(name)
        if part is None:
            continue
        held = _files(root, part.code)
        within = f"`[parts.{name}]`'s code in `settings.toml`"
        stamping = {
            d: part.stage >= project.STAMPED_FROM[d.name]
            and (kinds is None or d.name in kinds)
            for d in (SURFACES, COMMENTS, WHOOPSES, CATALOG)
        }
        fronted = (
            frontend.facts([p for _, p in held if p.suffix in frontend.SUFFIXES], root)
            if stamping[SURFACES] or stamping[COMMENTS]
            else []
        )
        scripted = (
            [bash.facts(p, root) for _, p in held if p.suffix in bash.SUFFIXES]
            if stamping[SURFACES] or stamping[COMMENTS]
            else []
        )
        if stamping[SURFACES]:
            python = _sorted(
                e
                for module, code in _modules(codes, root, part.code)
                for _, e in surfaces.entries(
                    code,
                    traces.setdefault(code.src, Trace(code, _FINDING, _WHOOPS)),
                    module,
                    root,
                )
            )
            shells = _sorted(e for f in scripted for e in f.surface)
            shown = _sorted(e for f in fronted for e in f.surface)
            legends = [
                (language, legend)
                for language, legend, entries in (
                    ("Python", surfaces.LEGEND, python),
                    ("bash", bash.LEGEND, shells),
                    ("TypeScript and Svelte", frontend.LEGEND, shown),
                )
                if entries
            ]
            if python or shells or shown or _modules(codes, root, part.code):
                written = surfaces.surfaced(
                    name, within, legends, [*python, *shells, *shown]
                )
                found.append(_proof(SURFACES / f"{name}.md", written))
        if stamping[COMMENTS]:
            read = [
                anchored.read(_code(codes, root, p), p, root)
                for _, p in held
                if p.suffix in (".py", *anchored.SCANNED)
            ]
            if read := [*read, *scripted, *fronted]:
                found.append(
                    _proof(
                        COMMENTS / f"{name}.md", anchored.commented(name, within, read)
                    )
                )
        if stamping[WHOOPSES]:
            python_files = [(h, p, c) for h, p in held if (c := _code(codes, root, p))]
            claimed = [
                anchored.claimed(code, p, root, _WHOOPS)
                for h, p, code in python_files
                if not anchored.tested(p, h if h.is_dir() else h.parent)
            ]
            if python_files:
                found.append(
                    _proof(
                        WHOOPSES / f"{name}.md", anchored.whooped(name, within, claimed)
                    )
                )
        if stamping[CATALOG]:
            said = said or [locale.extracted(root)]
            files = {str(p.relative_to(root)) for _, p in held}
            if any(w in files for m in said[0] for w, _ in m.locations):
                found.append(
                    _proof(
                        CATALOG / f"{name}.md",
                        anchored.cataloged(name, within, files, said[0]),
                    )
                )
    return found


def _sorted(entries: Iterable[Entry]) -> list[Entry]:
    return sorted(entries, key=lambda e: (e.name.casefold(), e.name))


def _modules(
    codes: dict[Path, Code], root: Path, code: Sequence[str]
) -> list[tuple[str, Code]]:
    found: list[tuple[str, Code]] = []
    for c in code:
        where = Path(c)
        package = project.PACKAGES.get(where.parent)
        if package is None or not (root / where.parent).is_dir():
            continue
        if not codes.get(where.parent):
            codes[where.parent] = Code(root / where.parent.parent, package)
        module = f"{package}.{where.stem}"
        if codes[where.parent].get(module) is not None:
            found.append((module, codes[where.parent]))
    return found


# Policy: what git keeps or would add, so that what a tool writes and git ignores, such as
# frontend/src/lib/api/schema.d.ts, isn't read, and what [index] left_out names neither.
def _files(root: Path, code: Sequence[str]) -> list[tuple[Path, Path]]:
    """Each file of the code, with the entry of the code it is in."""
    if not code:
        return []
    entries = [root / c for c in code]
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
            + ["--", *code],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split("\0")
        files = sorted({root / p for p in listed if p})
    except (OSError, subprocess.CalledProcessError):
        files = sorted(
            {p for h in entries for p in ([h] if h.is_file() else h.rglob("*"))}
        )
    left = [root / p for p in project.LEFT_OUT]
    held: list[tuple[Path, Path]] = []
    for p in files:
        if not p.is_file() or any(o == p or o in p.parents for o in left):
            continue
        entry = next(e for e in entries if e == p or e in p.parents)
        held.append((entry, p))
    return held


def _proof(path: Path, written: str) -> Proof:
    current = path.read_text() if path.exists() else None
    try:
        return Proof(path, current, stamped(current, written))
    except ValueError as e:
        raise ValueError(f"{_shown(path)}: {e}") from None


def _code(codes: dict[Path, Code], root: Path, path: Path) -> Code | None:
    if path.suffix != ".py":
        return None
    held = [
        (where, name)
        for where, name in project.PACKAGES.items()
        if (root / where) in path.parents
    ]
    if not held:
        return None
    [(where, name)] = held
    if where not in codes:
        codes[where] = Code(root / where.parent, name)
    return codes[where]


def facts(paths: Sequence[Path]) -> str:
    """The facts of each file as JSON, a Python file's read with the package it is in,
    whatever reads its language failing the call for one it can't read."""
    root = project.PROJECT_ROOT
    codes: dict[Path, Code] = {}
    read: list[Facts] = []
    for path in (p.resolve() for p in paths):
        code = _code(codes, root, path)
        if path.suffix == ".py" and code is None:
            raise SystemExit(f"facts: {path}: in no package")
        if path.suffix in frontend.SUFFIXES:
            read += frontend.facts([path], root)
        elif path.suffix in (".py", *bash.SUFFIXES, *anchored.SCANNED):
            read.append(anchored.read(code, path, root))
        else:
            raise SystemExit(f"facts: {path}: nothing reads it")
    return dumped(read)


def check(parts: Sequence[str] = (), kinds: Sequence[str] = ()) -> None:
    """Fails, saying which, while an index is behind the code, and, of all of them, flags
    what parts hold amiss: code no part holds, or two do, or that isn't there, and docs no
    part has or writes."""
    flags: list[str] = []
    try:
        found = proofs(parts or None, kinds or None)
    except ValueError as e:
        found, flags = [], [str(e)]
    else:
        if not parts and not kinds:
            flags += _strays({s.path for s in found})
    for flag in flags:
        print(f"flag: {flag}", file=sys.stderr)
    behind = [s for s in found if s.behind]
    if behind:
        shown = ", ".join(_shown(s.path) for s in behind)
        raise SystemExit(f"index: {shown} behind the code: run chatddx-dev index")
    if flags:
        raise SystemExit(1)
    print("ok")


def write(parts: Sequence[str] = (), kinds: Sequence[str] = ()) -> None:
    """Writes each index behind the code, saying how many stamps."""
    try:
        found = proofs(parts or None, kinds or None)
    except ValueError as e:
        raise SystemExit(f"index: {e}") from None
    written: list[str] = []
    for s in found:
        if not s.behind:
            continue
        s.path.parent.mkdir(parents=True, exist_ok=True)
        _ = s.path.write_text(s.written)
        written.append(
            f"{_shown(s.path)}: {'new' if s.current is None else _stamps(s.new)}"
        )
    print("\n".join(written) or "nothing to write")


# Policy: a unit is held whole by a part, or split among parts file by file, so that a
# page's own files can be another part's than the package they are in.
def _held(unit: Path, held: list[Path]) -> bool:
    def holding(p: Path) -> bool:
        return any(h == p or h in p.parents for h in held)

    if holding(unit):
        return True
    files = [f for f in unit.rglob("*") if f.is_file() and "__pycache__" not in f.parts]
    return unit.is_dir() and bool(files) and all(holding(f) for f in files)


def _strays(written: set[Path]) -> list[str]:
    root = project.PROJECT_ROOT
    units = [
        p.parent for src in project.PACKAGES for p in (root / src).glob("*/__init__.py")
    ]
    units += [
        p
        for src in project.PACKAGES
        for p in (root / src).glob("*.py")
        if p.stem != "__init__"
    ]
    units += [p for d in _FRONTEND for p in (root / d).glob("*")]
    held = [(name, root / c) for name, part in project.PARTS.items() for c in part.code]
    docs = {root / p.doc: name for name, p in project.PARTS.items() if p.doc}
    generated = [
        p for docs in (SURFACES, COMMENTS, WHOOPSES, CATALOG) for p in docs.glob("*.md")
    ]
    return (
        [
            f"{_shown(p)}: no part's code in project.PARTS holds it"
            for p in sorted(units)
            if not _held(p, [h for _, h in held])
        ]
        + [
            f"{_shown(p)}: in {name}'s code, but isn't there"
            for name, p in held
            if not p.exists()
        ]
        + [
            f"{_shown(p)}: held by {name} and {other}"
            for i, (name, p) in enumerate(held)
            for other, q in held[i + 1 :]
            if p == q or p in q.parents or q in p.parents
        ]
        + [
            f"{_shown(p)}: no part in project.PARTS has it as its doc"
            for p in sorted(PARTS.glob("*.md"))
            if p not in docs
        ]
        + [
            f"{_shown(p)}: {name}'s doc, but isn't there"
            for p, name in sorted(docs.items())
            if not p.exists()
        ]
        + [
            f"{_shown(p)}: no part writes it at its stage"
            for p in sorted(generated)
            if p not in written
        ]
    )


def _shown(path: Path) -> str:
    return str(path.relative_to(project.PROJECT_ROOT))


def _stamps(count: int) -> str:
    return f"{count} stamp" if count == 1 else f"{count} stamps"
