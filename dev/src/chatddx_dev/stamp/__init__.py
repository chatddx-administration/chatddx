import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

from chatddx import locale
from chatddx.markers import applied, restamped, signed
from chatddx_dev import project
from chatddx_dev.index import CATALOG, COMMENTS, SURFACES, WHOOPSES, Proof

__all__ = ["check", "docs", "documents", "pending", "reflow"]

_PRETTIER = project.PROJECT_ROOT / "frontend" / "node_modules" / ".bin" / "prettier"


def documents() -> list[Path]:
    root, written = project.PROJECT_ROOT, {SURFACES, COMMENTS, WHOOPSES, CATALOG}
    found = [p for p in (root / "docs").rglob("*.md") if not written & set(p.parents)]
    found += [root / "AGENTS.md", root / "README.md"]
    return sorted(p for p in found if p.is_file())


def check() -> None:
    """Fails, saying which, while a doc, an index or a catalog holds a conflict that isn't
    a stamp, or a stamp that isn't closed."""
    try:
        _ = _held(sorted([*_indexes(), *documents(), *locale.catalogs()]))
    except ValueError as e:
        raise SystemExit(f"stamp: {e}") from None
    print("ok")


def _indexes() -> list[Path]:
    return [
        p for docs in (SURFACES, COMMENTS, WHOOPSES, CATALOG) for p in docs.glob("*.md")
    ]


def pending() -> None:
    try:
        held = _held(sorted([*_indexes(), *documents(), *locale.catalogs()]))
    except ValueError as e:
        raise SystemExit(f"stamp pending: {e}") from None
    flags = [
        f"{_shown(s.path)}: {_stamps(s.pending)} pending" for s in held if s.pending
    ]
    for flag in flags:
        print(f"flag: {flag}", file=sys.stderr)
    if flags:
        raise SystemExit(1)
    print("ok")


def docs(base: str, check: bool = False) -> None:
    root = project.PROJECT_ROOT
    base = _git(root, "rev-parse", "--verify", f"{base}^{{commit}}").strip()
    shown = _git(root, "log", "-1", "--format=%h %s", base).strip()
    ours, catalogs = set(documents()), set(locale.catalogs())
    print(f"against {shown}")
    written: list[str] = []
    behind: list[str] = []
    for path, was in _changed(root, base):
        if path not in ours | catalogs:
            continue
        current = path.read_text()
        then = None if was is None else _git(root, "show", f"{base}:{was}")
        try:
            if path in catalogs:
                s = Proof(
                    path, current, locale.restamped(path.stem, then, current, root)
                )
            else:
                s = Proof(path, current, restamped(then, current))
        except ValueError as e:
            raise SystemExit(f"stamp docs: {_shown(path)}: {e}") from None
        if s.behind and check:
            behind.append(_shown(path))
        elif s.behind:
            _ = path.write_text(s.written)
            written.append(f"{_shown(path)}: {_stamps(s.new)}")
    if behind:
        listed = ", ".join(behind)
        raise SystemExit(f"stamp docs: {listed} behind: run ./dev/write.sh stamps")
    print("ok" if check else "\n".join(written) or "nothing to write")


# Policy: prettier reads a stamp's markers as markdown, so a doc holding stamps pending is
# reflowed a side at a time, the side last stamped and the side written now, each as a doc
# of its own, and stamped again from the two.
def reflow(check: bool) -> None:
    root = project.PROJECT_ROOT
    try:
        held = [s for s in _held(documents()) if s.pending]
    except ValueError as e:
        raise SystemExit(f"stamp reflow: {e}") from None
    shown = [_shown(s.path) for s in held]
    # Accommodating for prettier, which lists what differs at its log level, so that any
    # quieter level lists nothing and passes.
    mode = (
        ["--list-different", "--log-level", "log"]
        if check
        else ["--write", "--log-level", "warn"]
    )
    done = subprocess.run(
        [_PRETTIER, *mode, ".", *(f"!{name}" for name in shown)],
        cwd=root,
        stdout=subprocess.PIPE if check else None,
        text=True,
        check=False,
    )
    if done.returncode not in ((0, 1) if check else (0,)):
        raise SystemExit(done.returncode)
    unformatted = done.stdout.splitlines() if check else []
    for s, name in zip(held, shown, strict=True):
        text = s.current or ""
        was = [signed(text), applied(text)]
        now = [_prettier(root, name, side) for side in was]
        if now == was:
            continue
        if check:
            unformatted.append(name)
        else:
            last, written = ("\n".join(side) + "\n" for side in now)
            _ = s.path.write_text(restamped(last, written))
    if unformatted:
        listed = ", ".join(sorted(unformatted))
        raise SystemExit(
            f"stamp reflow: {listed} unformatted: run chatddx-dev stamp reflow"
        )


def _prettier(root: Path, name: str, lines: list[str]) -> list[str]:
    done = subprocess.run(
        [_PRETTIER, "--stdin-filepath", name],
        cwd=root,
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode:
        raise SystemExit(f"stamp reflow: {name}: {done.stderr.strip()}")
    return done.stdout.splitlines()


def _held(paths: Iterable[Path]) -> list[Proof]:
    found: list[Proof] = []
    for path in paths:
        text = path.read_text()
        try:
            _ = signed(text)
        except ValueError as e:
            raise ValueError(f"{_shown(path)}: {e}") from None
        found.append(Proof(path, text, text))
    return found


def _changed(root: Path, base: str) -> list[tuple[Path, str | None]]:
    found: list[tuple[Path, str | None]] = []
    fields = iter(_git(root, "diff", "-z", "--name-status", "-M", base).split("\0"))
    for status in fields:
        if status.startswith("R"):
            was = next(fields)
            found.append((root / next(fields), was))
        elif status in ("A", "M", "T"):
            name = next(fields)
            found.append((root / name, None if status == "A" else name))
        elif status:
            _ = next(fields)
    others = _git(root, "ls-files", "-z", "--others", "--exclude-standard")
    found += [(root / name, None) for name in others.split("\0") if name]
    return found


def _git(root: Path, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"stamp docs: git {args[0]}: {e.stderr.strip()}") from None
    return done.stdout


def _shown(path: Path) -> str:
    return str(path.relative_to(project.PROJECT_ROOT))


def _stamps(count: int) -> str:
    return f"{count} stamp" if count == 1 else f"{count} stamps"
