# `dev`

Written by `chatddx-dev index` from `[parts.dev]`'s code in `settings.toml`, an entry for each public name, sorted alphabetically whatever its case, so that a class's members follow it, a language's after another's:

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

bash:

```
## `<script or function>`
`<file>:<function>`

<its usage, as the comment above it says>

* `<command>`
* `$<positional parameter>`
* `$<variable from the environment>`
```

- A command, a script with a shebang or a top-level `case` on its first argument, is an entry named after its file, its usage the comment it begins with, its commands what that `case` dispatches; any other script is sourced, an entry for each of its functions, its usage the comment right above it. A bats test is no entry.
- The environment is what it reads in capitals and never assigns nor names, bash's own, `PATH`, `HOME` and `PWD` left out.

- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `beside`
`dev/src/chatddx_dev/project.py:beside`

How many of dev/check.sh's other checks run beside this one, as it says.

* ∟`int`

## `Class` `(StrEnum)`
`dev/src/chatddx_dev/project.py:Class`

* `DATAMODEL = "datamodel"`
* `UX = "ux"`
* `MACHINERY = "machinery"`

## `COSTS_QUOTED`
`dev/src/chatddx_dev/project.py:COSTS_QUOTED`

`COSTS_QUOTED: str = _HELD["costs"]["quoted"]`

## `COSTS_QUOTED_IN`
`dev/src/chatddx_dev/project.py:COSTS_QUOTED_IN`

`COSTS_QUOTED_IN: list[str] = _HELD["costs"]["quoted_in"]`

## `LEFT_OUT`
`dev/src/chatddx_dev/project.py:LEFT_OUT`

`LEFT_OUT: list[str] = _HELD["index"]["left_out"]`

## `machine_class`
`dev/src/chatddx_dev/project.py:machine_class`

* ∟`str | None`

## `main`
`dev/src/chatddx_dev/main.py:main`

* `argv: Sequence[str] | None = None`
* ∟`None`

## `PACKAGES`
`dev/src/chatddx_dev/project.py:PACKAGES`

`PACKAGES = {Path("src/chatddx"): "chatddx", Path("dev/src/chatddx_dev"): "chatddx_dev"}`

## `Part` `@dataclass(frozen=True)`
`dev/src/chatddx_dev/project.py:Part`

* `stage: Stage`
* `class_: Class`
* `doc: str | None`
* `code: tuple[str, ...]`

## `PARTS`
`dev/src/chatddx_dev/project.py:PARTS`

`PARTS = …`

## `Stage` `(IntEnum)`
`dev/src/chatddx_dev/project.py:Stage`

* `FELT = 1`
* `IMPLIED = 2`
* `MENTIONED = 3`
* `NAMED = 4`
* `ITEMIZED = 5`
* `PLANNED = 6`
* `DRAFTED = 7`
* `SOLIDIFIED = 8`
* `CEMENTED = 9`
* `PROTECTED = 10`

## `STAMPED_FROM`
`dev/src/chatddx_dev/project.py:STAMPED_FROM`

`STAMPED_FROM = …`

## `agent.sh`
`dev/agent.sh`

* `session-start`
* `turn-start`
* `turn-end`
* `hand-over`
* `provision`
* `$CLAUDE_CODE_REMOTE`
* `$CLAUDE_ENV_FILE`

## `check.sh`
`dev/check.sh`

Usage: ./dev/check.sh [check]..., from the repository's root in the dev shell with its database
up (dev-db start). Each check tests one thing and writes nothing git tracks; the checks
named, or all of them, run side by side, and it fails, saying which did, if any does.
What a check that runs says is also logged to dev/state/logs/<check>.log, as dev/write.sh moves it to logs/.

* `$MACHINE_CLASS`

## `dev-db.sh`
`dev/dev-db.sh`

* `start`
* `stop`
* `status`
* `enter`
* `reset`
* `$CHATDDX_STATE_HOME`
* `$REPO_ROOT`

## `operator.sh`
`dev/operator.sh`

* `fetch`
* `stamp`
* `merge`
* `$CHATDDX_DEV`
* `$MAIN`

## `setting`
`dev/settings.sh:setting`

Usage: . dev/settings.sh, then setting <array> <key>, from the repository's root: sets the array to the words
settings.toml holds at the dotted key.

* `$1`
* `$2`

## `stamped`
`dev/stamped.sh:stamped`

Usage: . dev/stamped.sh, from the repository's root, then stamped [guessed]: prints the commit stamps are made
against: $STAMPED, or else what refs/stamped/<branch> holds, as ./dev/operator.sh stamp sets it, while HEAD is on it.
Given guessed, it falls back to where HEAD left main, and fails, saying why, if there is none either. Outside a git
checkout it prints nothing.
Policy: the guess errs on stamping again: main is stamped, as ./dev/operator.sh merge squashes onto it, and where HEAD
left it comes before anything stamped on the branch, so that what was stamped since is stamped again, not left out.

* `$1`
* `$MAIN`
* `$STAMPED`

## `write.sh`
`dev/write.sh`

Usage: [STAMPED=<commit>] ./dev/write.sh [write]..., from the repository's root in the dev
shell. Writes the writes named, or all of them, one after the other in the order of WRITES,
what follows from the code and the docs, and says what it wrote, stopping at the first that
fails. Each but costs and logs writes what the check of its name checks; stamps writes the
prose's against the commit dev/stamped.sh tells, or guesses.
