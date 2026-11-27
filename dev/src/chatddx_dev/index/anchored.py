import ast
import io
import re
import tokenize
from collections.abc import Iterable, Sequence
from dataclasses import replace
from pathlib import Path
from textwrap import dedent

import griffe
from babel.messages.catalog import Catalog

from chatddx.markers import PENDING

from .bash import SUFFIXES as SHELL, facts as shell
from .code import Code
from .facts import Claim, Comment, Facts, Named

# Compromise: what isn't Python is read by its strings and comments alone: a body in
# dollar quotes is read as SQL, as a function's body is, and an E'' string's \' throws
# the reading off.
SCANNED = {
    ".sql": re.compile(
        r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|(--[^\n]*|/\*.*?\*/)", re.DOTALL
    ),
    ".toml": re.compile(
        r'"""(?:[^\\]|\\.)*?"""|\'\'\'.*?\'\'\'|"(?:[^"\\\n]|\\.)*"|\'[^\'\n]*\'|(#[^\n]*)',
        re.DOTALL,
    ),
}


def _tokenized(source: str) -> list[Comment]:
    return [
        Comment(
            t.start[0], t.start[1], t.string.rstrip(), not t.line[: t.start[1]].strip()
        )
        for t in tokenize.generate_tokens(io.StringIO(source).readline)
        if t.type == tokenize.COMMENT
    ]


def _scanned(source: str, pattern: re.Pattern[str]) -> list[Comment]:
    found: list[Comment] = []
    for m in pattern.finditer(source):
        if m.group(1) is None:
            continue
        begun = source.rfind("\n", 0, m.start(1)) + 1
        found.append(
            Comment(
                source.count("\n", 0, begun) + 1,
                m.start(1) - begun,
                m.group(1).rstrip(),
                not source[begun : m.start(1)].strip(),
            )
        )
    return found


def _blocks(found: Iterable[Comment]) -> list[list[Comment]]:
    blocks: list[list[Comment]] = []
    for c in found:
        last = blocks[-1][-1] if blocks else None
        if (
            last is not None
            and c.alone
            and last.alone
            and c.column == last.column
            and c.line == last.last + 1
        ):
            blocks[-1].append(c)
        else:
            blocks.append([c])
    return blocks


def _within(named: Iterable[Named], first: int, last: int) -> str:
    held = [(n.line, n.name) for n in named if n.line <= first and last <= n.end]
    return max(held)[1] if held else ""


def _anchor(named: tuple[Named, ...], block: list[Comment]) -> str:
    first, last = block[0], block[-1]
    if first.alone:
        for n in named:
            if n.line == last.last + 1 and n.column == first.column:
                return n.name
    return _within(named, first.line, last.last)


def read(code: Code | None, path: Path, repo: Path) -> Facts:
    """A file's facts as the index reads them: Python's by its names and comments, bash's
    and bats' as shfmt parses them, SQL's and TOML's by their comments alone."""
    shown = str(path.relative_to(repo))
    if path.suffix in SHELL:
        return shell(path, repo)
    if path.suffix != ".py":
        return Facts(
            shown, (), tuple(_scanned(path.read_text(), SCANNED[path.suffix])), ()
        )
    assert code is not None, "a Python file is read with the package it is in"
    file = code.file(path)
    named = tuple(
        Named(name, begun, ended, column) for name, begun, ended, column in file.names
    )
    return Facts(shown, named, tuple(_tokenized(file.source)), ())


def _held(facts: Iterable[Facts]) -> dict[tuple[str, str], list[list[str]]]:
    held: dict[tuple[str, str], list[list[str]]] = {}
    for f in facts:
        for block in _blocks(f.comments):
            fenced = _fenced("\n".join(c.text for c in block))
            held.setdefault((f.path, _anchor(f.names, block)), []).append(fenced)
    return held


def _fenced(held: str) -> list[str]:
    fence = "`" * max([3, *(len(run) + 1 for run in re.findall("`+", held))])
    return [fence, *held.splitlines(), fence]


def _written(heading: list[str], held: dict[tuple[str, str], list[list[str]]]) -> str:
    lines = list(heading)
    for shown, anchor in sorted(held, key=lambda k: (k[0], k[1].casefold(), k[1])):
        lines += ["", f"## `{shown}:{anchor}`" if anchor else f"## `{shown}`"]
        for fenced in held[shown, anchor]:
            lines += ["", *fenced]
    return "\n".join(lines) + "\n"


def commented(name: str, within: str, facts: Iterable[Facts]) -> str:
    """The index of the comments in what facts were read off, named and said to be from
    within."""
    return _written(
        [
            f"# Comments in `{name}`",
            "",
            f"Written by `chatddx-dev index` from the comments in {within}, sorted by "
            + "file and then by name whatever its case:",
            "",
            "````",
            "## `<file>:<the name it is in or right above>`",
            "",
            "```",
            "<the comment, as written>",
            "```",
            "````",
            "",
            "- A comment in or above no name is under its file alone, and comments on lines "
            + "one after another are one.",
            PENDING,
        ],
        _held(facts),
    )


def _claimed(code: Code, module: griffe.Module, node: ast.AST, whoops: str) -> bool:
    if isinstance(node, ast.Assert):
        return True
    if not isinstance(node, ast.Raise) or node.exc is None:
        return False
    target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
    kind = code.lookup(module, target)
    return kind is not None and code.subclass(kind, whoops)


def _claims(code: Code, path: Path, whoops: str) -> tuple[Claim, ...]:
    file = code.file(path)
    parts = path.relative_to(code.src).with_suffix("").parts
    module = code.get(".".join(parts[:-1] if parts[-1] == "__init__" else parts))
    assert isinstance(module, griffe.Module)
    found = [
        Claim(
            node.lineno,
            node.col_offset,
            node.end_lineno or node.lineno,
            dedent(file.segment(node, padded=True) or ""),
        )
        for node in ast.walk(file.tree)
        if isinstance(node, ast.stmt) and _claimed(code, module, node, whoops)
    ]
    return tuple(sorted(found, key=lambda c: (c.line, c.column)))


def tested(path: Path, within: Path) -> bool:
    """Whether a file is a test's, as found within a directory."""
    return (
        "test" in path.relative_to(within).parts[:-1]
        or path.name == "conftest.py"
        or path.name.startswith("test_")
    )


def claimed(code: Code, path: Path, repo: Path, whoops: str) -> Facts:
    """A Python file's facts with its claims: its asserts and what it raises of whoops or
    its subclasses."""
    return replace(read(code, path, repo), claims=_claims(code, path, whoops))


def whooped(name: str, within: str, facts: Iterable[Facts]) -> str:
    """The index of the claims in what facts were read off, named and said to be from
    within."""
    held: dict[tuple[str, str], list[list[str]]] = {}
    for f in facts:
        for c in f.claims:
            anchor = _within(f.names, c.line, c.end)
            held.setdefault((f.path, anchor), []).append(_fenced(c.text))
    return _written(
        [
            f"# Whoopses and asserts in `{name}`",
            "",
            "Written by `chatddx-dev index` from the `raise Whoops` and `assert` "
            + f"statements in {within}, its tests left out, sorted by file and then by "
            + "name whatever its case:",
            "",
            "````",
            "## `<file>:<the name it is in>`",
            "",
            "```",
            "<the statement, as written>",
            "```",
            "````",
            "",
            "- A statement in no name is under its file alone, and a `Whoops` is any of its "
            + "subclasses too.",
            PENDING,
        ],
        held,
    )


def cataloged(name: str, within: str, files: Iterable[str], said: Catalog) -> str:
    """The index of the messages said in files, as a catalog extracted them, named and
    said to be from within."""
    held: dict[tuple[str, str], list[list[str]]] = {}
    shown = set(files)
    for m in sorted(
        (m for m in said if m.id),
        key=lambda m: (_singular(m.id).casefold(), _singular(m.id), m.context or ""),
    ):
        forms = [m.id] if isinstance(m.id, str) else list(m.id)
        entry = [] if m.context is None else [f"`{m.context}`", ""]
        for i, form in enumerate(forms):
            entry += ([""] if i else []) + _fenced(form)
        for where in sorted({w for w, _ in m.locations if w in shown}):
            held.setdefault((where, ""), []).append(entry)
    return _written(
        [
            f"# What `{name}` says",
            "",
            f"Written by `chatddx-dev index` from the messages said in {within}, "
            + "its tests left out, as `chatddx locale write` extracts them into the "
            + "catalogs, sorted by file and then by message whatever its case:",
            "",
            "````",
            "## `<file>`",
            "",
            "`<its context>`",
            "",
            "```",
            "<the message, as written>",
            "```",
            "",
            "```",
            "<its plural>",
            "```",
            "````",
            "",
            "- A message said in no context has none before it, and one not counted no "
            + "plural after it.",
            PENDING,
        ],
        held,
    )


def _singular(msgid: str | Sequence[str]) -> str:
    return msgid if isinstance(msgid, str) else msgid[0]
