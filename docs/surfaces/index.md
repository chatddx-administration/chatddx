# `index`

Written by `chatddx-dev index` from `[parts.index]`'s code in `settings.toml`, an entry for each public name, sorted alphabetically whatever its case, so that a class's members follow it, a language's after another's:

Python:

```
## `<name>` `@<decorator>` `[<type parameters>]` `(<bases>)`
`<file>:<qualified name>`

* `<parameter or field>: <type> = <default>`
* ∟`<return type>`

Raises:
1. `<exception>`: `<arguments>` (from `<exception caught>`, through `<private helper>`, in a `ValidationError`)

Finds:
1. `<code>`: `<message>` (`<level>`, from `<exception caught>`, through `<private helper>`)
```

- A constant or a type alias is its definition instead of bullets; a class and its `__init__` leave out ∟, and a method its instance; `*`: the parameters after it are keyword-only, `/`: those before it positional-only.
- Raises and Finds are the function's own and its private helpers', in the order the code reaches them, each once, a `Whoops` left out; what a public function it calls raises is in that function's entry.
- Text is quoted, a value in it as `{<expression>}`, and an argument that isn't text is as written; a finding is a warning unless it gives its level.

- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `CATALOG`
`dev/src/chatddx_dev/index/__init__.py:CATALOG`

`CATALOG = project.PROJECT_ROOT / "docs" / "catalog"`

## `cataloged`
`dev/src/chatddx_dev/index/anchored.py:cataloged`

The index of the messages said in files, as a catalog extracted them, named and
said to be from within.

* `name: str`
* `within: str`
* `files: Iterable[str]`
* `said: Catalog`
* ∟`str`

## `check`
`dev/src/chatddx_dev/index/__init__.py:check`

Fails, saying which, while an index is behind the code, and, of all of them, flags
what parts hold amiss: code no part holds, or two do, or that isn't there, and docs no
part has or writes.

* `parts: Sequence[str] = ()`
* `kinds: Sequence[str] = ()`
* ∟`None`

Raises:
1. `SystemExit`: `"index: {shown} behind the code: run chatddx-dev index"`
2. `SystemExit`: `1`

## `Claim` `@dataclass(frozen=True)`
`dev/src/chatddx_dev/index/facts.py:Claim`

* `line: int`
* `column: int`
* `end: int`
* `text: str`

## `claimed`
`dev/src/chatddx_dev/index/anchored.py:claimed`

A Python file's facts with its claims: its asserts and what it raises of whoops or
its subclasses.

* `code: Code`
* `path: Path`
* `repo: Path`
* `whoops: str`
* ∟`Facts`

## `Code`
`dev/src/chatddx_dev/index/code.py:Code`

* `src: Path`
* `root: griffe.Module`

## `Code.__init__`
`dev/src/chatddx_dev/index/code.py:Code.__init__`

* `src: Path`
* `package: str`

## `Code.bases`
`dev/src/chatddx_dev/index/code.py:Code.bases`

* `cls: griffe.Class`
* ∟`list[str]`

## `Code.file`
`dev/src/chatddx_dev/index/code.py:Code.file`

* `path: Path`
* ∟`File`

## `Code.get`
`dev/src/chatddx_dev/index/code.py:Code.get`

* `path: str`
* ∟`griffe.Object | None`

## `Code.handled`
`dev/src/chatddx_dev/index/code.py:Code.handled`

* `module: griffe.Module`
* `expr: ast.expr`
* ∟`list[str]`

## `Code.lines`
`dev/src/chatddx_dev/index/code.py:Code.lines`

* `obj: griffe.Object`
* ∟`list[str]`

## `Code.lookup`
`dev/src/chatddx_dev/index/code.py:Code.lookup`

* `module: griffe.Module`
* `expr: ast.expr`
* ∟`str | None`

## `Code.member`
`dev/src/chatddx_dev/index/code.py:Code.member`

* `cls: griffe.Class`
* `name: str`
* ∟`griffe.Object | None`

## `Code.named`
`dev/src/chatddx_dev/index/code.py:Code.named`

* `expr: griffe.ExprName`
* ∟`str`

## `Code.node`
`dev/src/chatddx_dev/index/code.py:Code.node`

* `obj: griffe.Object`
* ∟`Node`

## `Code.segment`
`dev/src/chatddx_dev/index/code.py:Code.segment`

* `obj: griffe.Object`
* `node: Spanned`
* ∟`str`

## `Code.source`
`dev/src/chatddx_dev/index/code.py:Code.source`

* `obj: griffe.Object`
* `node: Spanned`
* ∟`str | None`

## `Code.subclass`
`dev/src/chatddx_dev/index/code.py:Code.subclass`

* `path: str`
* `of: str`
* ∟`bool`

## `Code.text`
`dev/src/chatddx_dev/index/code.py:Code.text`

* `module: griffe.Module`
* `expr: ast.expr`
* ∟`str | None`

## `Comment` `@dataclass(frozen=True)`
`dev/src/chatddx_dev/index/facts.py:Comment`

* `line: int`
* `column: int`
* `text: str`
* `alone: bool`

## `Comment.last` `@property`
`dev/src/chatddx_dev/index/facts.py:Comment.last`

* ∟`int`

## `commented`
`dev/src/chatddx_dev/index/anchored.py:commented`

The index of the comments in what facts were read off, named and said to be from
within.

* `name: str`
* `within: str`
* `facts: Iterable[Facts]`
* ∟`str`

## `COMMENTS`
`dev/src/chatddx_dev/index/__init__.py:COMMENTS`

`COMMENTS = project.PROJECT_ROOT / "docs" / "comments"`

## `decorated`
`dev/src/chatddx_dev/index/code.py:decorated`

* `node: Node`
* `names: frozenset[str]`
* ∟`bool`

## `Def`
`dev/src/chatddx_dev/index/code.py:Def`

`type Def = ast.FunctionDef | ast.AsyncFunctionDef`

## `dumped`
`dev/src/chatddx_dev/index/facts.py:dumped`

* `facts: list[Facts]`
* ∟`str`

## `entries`
`dev/src/chatddx_dev/index/surfaces.py:entries`

The surface's entries of a module and what is in it, each with its file, an entry
for each public name, sorted alphabetically whatever its case, so that a class's
members follow it; what it raises and finds traced through its private helpers.

* `code: Code`
* `trace: Trace`
* `package: str`
* `repo: Path`
* ∟`list[tuple[str, Entry]]`

## `Entry` `@dataclass(frozen=True)`
`dev/src/chatddx_dev/index/facts.py:Entry`

A public name's entry in a surface, as its extractor renders it: the name it sorts
by, its heading, and its lines below the heading.

* `name: str`
* `heading: str`
* `lines: tuple[str, ...]`

## `EXTRACTOR`
`dev/src/chatddx_dev/index/frontend.py:EXTRACTOR`

`EXTRACTOR = project.PROJECT_ROOT / "frontend" / "scripts" / "facts.mjs"`

## `Facts` `@dataclass(frozen=True)`
`dev/src/chatddx_dev/index/facts.py:Facts`

What an extractor read off a file, whatever its language: the names it defines
and the lines they span, its comments, and the statements a whoops index lists, with
lines from 1 and columns from 0, for the index to anchor each to the name it is in or
right above; and its surface's entries, as rendered.

* `path: str`
* `names: tuple[Named, ...]`
* `comments: tuple[Comment, ...]`
* `claims: tuple[Claim, ...]`
* `surface: tuple[Entry, ...] = ()`

## `bash.facts`
`dev/src/chatddx_dev/index/bash.py:facts`

The functions, tests, top-level assignments and comments of a bash or bats file,
its shebang left out, as shfmt parses it, which runs once for it.

* `path: Path`
* `repo: Path`
* ∟`Facts`

Raises:
1. `SystemExit`: `"stamp: shfmt: {e.stderr.strip()}"` (from `subprocess.CalledProcessError`)

## `frontend.facts`
`dev/src/chatddx_dev/index/frontend.py:facts`

The names and comments of TypeScript and Svelte files, as the frontend's
extractor reads them with TypeScript's and Svelte's parsers, in one run of node.

* `paths: Sequence[Path]`
* `repo: Path`
* ∟`list[Facts]`

Raises:
1. `SystemExit`: `"stamp: {EXTRACTOR.name}: {e.stderr.strip()}"` (from `subprocess.CalledProcessError`)

## `File` `@dataclass(frozen=True)`
`dev/src/chatddx_dev/index/code.py:File`

* `source: str`
* `tree: ast.Module`

## `File.lines` `@cached_property`
`dev/src/chatddx_dev/index/code.py:File.lines`

* ∟`list[str]`

## `File.names` `@cached_property`
`dev/src/chatddx_dev/index/code.py:File.names`

* ∟`list[tuple[str, int, int, int]]`

## `File.nodes` `@cached_property`
`dev/src/chatddx_dev/index/code.py:File.nodes`

* ∟`dict[int, Node]`

## `File.segment`
`dev/src/chatddx_dev/index/code.py:File.segment`

* `node: Spanned`
* `padded: bool = False`
* ∟`str | None`

## `Found` `@dataclass(frozen=True)`
`dev/src/chatddx_dev/index/trace.py:Found`

* `code: str`
* `message: str | None`
* `level: str | None = None`
* `through: str | None = None`
* `origin: str | None = None`

## `KINDS`
`dev/src/chatddx_dev/index/__init__.py:KINDS`

`KINDS = ("catalog", "comments", "surfaces", "whoopses")`

## `bash.LEGEND`
`dev/src/chatddx_dev/index/bash.py:LEGEND`

`LEGEND = […]`

## `frontend.LEGEND`
`dev/src/chatddx_dev/index/frontend.py:LEGEND`

`LEGEND = […]`

## `surfaces.LEGEND`
`dev/src/chatddx_dev/index/surfaces.py:LEGEND`

`LEGEND = […]`

## `loaded`
`dev/src/chatddx_dev/index/facts.py:loaded`

Facts as dumped writes them, as an extractor in another language prints them.

* `text: str`
* ∟`list[Facts]`

## `Named` `@dataclass(frozen=True)`
`dev/src/chatddx_dev/index/facts.py:Named`

* `name: str`
* `line: int`
* `end: int`
* `column: int`

## `Node`
`dev/src/chatddx_dev/index/code.py:Node`

`type Node = Def | ast.ClassDef`

## `PARTS`
`dev/src/chatddx_dev/index/__init__.py:PARTS`

`PARTS = project.PROJECT_ROOT / "docs" / "parts"`

## `private`
`dev/src/chatddx_dev/index/code.py:private`

* `name: str`
* ∟`bool`

## `Proof` `@dataclass(frozen=True)`
`dev/src/chatddx_dev/index/__init__.py:Proof`

* `path: Path`
* `current: str | None`
* `written: str`

## `Proof.behind` `@property`
`dev/src/chatddx_dev/index/__init__.py:Proof.behind`

* ∟`bool`

## `Proof.new` `@property`
`dev/src/chatddx_dev/index/__init__.py:Proof.new`

* ∟`int`

## `Proof.pending` `@property`
`dev/src/chatddx_dev/index/__init__.py:Proof.pending`

* ∟`int`

## `proofs`
`dev/src/chatddx_dev/index/__init__.py:proofs`

The surface, the comment index, the whoops index and the catalog of each part, or
each part named, or those of the kinds named, at a stage from which each is stamped,
whatever the language of its code: its Python modules' public names and the
frontend's exports and props; its comments in what Python, SQL, TOML, bash, bats,
TypeScript or Svelte is in it; its claims in its Python, and the messages it says,
its tests left out. Griffe reads each package once, shfmt each script once, node a
part's frontend once, and the locale's extraction the whole code once.

* `parts: Iterable[str] | None = None`
* `kinds: Iterable[str] | None = None`
* ∟`list[Proof]`

Raises:
1. `ValueError`: `"{_shown(path)}: {e}"` (from `ValueError`, through `_proof`)

## `Raised` `@dataclass(frozen=True)`
`dev/src/chatddx_dev/index/trace.py:Raised`

* `exception: str`
* `message: str | None`
* `kind: str | None`
* `through: str | None = None`
* `validated: bool = False`
* `origin: str | None = None`

## `read`
`dev/src/chatddx_dev/index/anchored.py:read`

A file's facts as the index reads them: Python's by its names and comments, bash's
and bats' as shfmt parses them, SQL's and TOML's by their comments alone.

* `code: Code | None`
* `path: Path`
* `repo: Path`
* ∟`Facts`

## `SCANNED`
`dev/src/chatddx_dev/index/anchored.py:SCANNED`

`SCANNED = {…}`

## `Spanned`
`dev/src/chatddx_dev/index/code.py:Spanned`

`type Spanned = ast.expr | ast.stmt | ast.type_param`

## `bash.SUFFIXES`
`dev/src/chatddx_dev/index/bash.py:SUFFIXES`

`SUFFIXES = {".sh": "bash", ".bats": "bats"}`

## `frontend.SUFFIXES`
`dev/src/chatddx_dev/index/frontend.py:SUFFIXES`

`SUFFIXES = (".ts", ".svelte")`

## `surface`
`dev/src/chatddx_dev/index/bash.py:surface`

A script's entry, as a command, or its functions', as a script sourced.

* `path: str`
* `source: str`
* `tree: dict[str, Any]`
* `comments: tuple[Comment, ...]`
* ∟`tuple[Entry, ...]`

## `surfaced`
`dev/src/chatddx_dev/index/surfaces.py:surfaced`

The surface named, said to be from within, of the entries in the order given, with
the legend of each language they are in, in that order.

* `name: str`
* `within: str`
* `legends: list[tuple[str, list[str]]]`
* `entries: list[Entry]`
* ∟`str`

## `SURFACES`
`dev/src/chatddx_dev/index/__init__.py:SURFACES`

`SURFACES = project.PROJECT_ROOT / "docs" / "surfaces"`

## `tested`
`dev/src/chatddx_dev/index/anchored.py:tested`

Whether a file is a test's, as found within a directory.

* `path: Path`
* `within: Path`
* ∟`bool`

## `Trace`
`dev/src/chatddx_dev/index/trace.py:Trace`

* `code: Code`
* `findings: tuple[str, str]`
* `whoops: str`

## `Trace.__init__`
`dev/src/chatddx_dev/index/trace.py:Trace.__init__`

* `code: Code`
* `finding: str`
* `whoops: str`

## `Trace.caught`
`dev/src/chatddx_dev/index/trace.py:Trace.caught`

* `kind: str | None`
* `caught: tuple[str, ...]`
* ∟`bool`

## `Trace.constructing`
`dev/src/chatddx_dev/index/trace.py:Trace.constructing`

* `cls: griffe.Class`
* ∟`tuple[Raised, ...]`

## `Trace.of`
`dev/src/chatddx_dev/index/trace.py:Trace.of`

* `function: griffe.Object`
* `cls: griffe.Class | None`
* ∟`Traced`

## `Traced` `@dataclass(frozen=True)`
`dev/src/chatddx_dev/index/trace.py:Traced`

* `raised: tuple[Raised, ...]`
* `found: tuple[Found, ...]`

## `VALIDATORS`
`dev/src/chatddx_dev/index/trace.py:VALIDATORS`

`VALIDATORS = frozenset(…)`

## `whooped`
`dev/src/chatddx_dev/index/anchored.py:whooped`

The index of the claims in what facts were read off, named and said to be from
within.

* `name: str`
* `within: str`
* `facts: Iterable[Facts]`
* ∟`str`

## `WHOOPSES`
`dev/src/chatddx_dev/index/__init__.py:WHOOPSES`

`WHOOPSES = project.PROJECT_ROOT / "docs" / "whoopses"`

## `write`
`dev/src/chatddx_dev/index/__init__.py:write`

Writes each index behind the code, saying how many stamps.

* `parts: Sequence[str] = ()`
* `kinds: Sequence[str] = ()`
* ∟`None`

Raises:
1. `SystemExit`: `"index: {e}"` (from `ValueError`)
