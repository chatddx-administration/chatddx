# Comments in `dev`

Written by `chatddx-dev index` from the comments in `[parts.dev]`'s code in `settings.toml`, sorted by file and then by name whatever its case:

````
## `<file>:<the name it is in or right above>`

```
<the comment, as written>
```
````

- A comment in or above no name is under its file alone, and comments on lines one after another are one.
- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `dev/agent.sh`

```
# Accommodating for Claude Code, which hands what session-start writes to $CLAUDE_ENV_FILE
# to the session's commands but not to its hooks.
```

```
# Accommodating for Claude Code, which adds what a hook says to the session only if it
# exits 0, and what a Stop hook says only if it exits 2.
```

## `dev/agent.sh:database`

```
# Heads-up: psycopg reads a SQL_ASCII database's text as bytes, which chatddx migrate
# takes for none of its migrations applied.
```

## `dev/agent.sh:event`

```
# Heads-up: the hooks alone set it from stdin; nounset needs it set for field elsewhere.
```

## `dev/agent.sh:fetched`

```
# Policy: refs/stamped/* comes along, as ./dev/operator.sh stamp pushes it, for what dev/stamped.sh
# tells is stamped.
```

## `dev/agent.sh:hand-over`

```
# Policy: the budget is told only once all pass, lest it be read as part of a failure.
```

## `dev/agent.sh:moved_logs`

```
# Duplication: dev/write.sh's move of the check logs.
# Accommodating for nixpkgs' non-interactive bash, which lacks compgen.
```

## `dev/agent.sh:provisioned`

```
# Accommodating for bash, which ignores errexit wherever a status is tested: provisioning
# runs as a process of its own, so that it still stops at its first failure.
```

## `dev/agent.sh:pushed`

```
# Policy: a branch rebased over what it pushed before is pushed over it, leased on the tip
# just fetched, so that nothing pushed since is lost.
```

## `dev/agent.sh:rebased`

```
# Policy: told by patch, as git cherry tells it, so that a rebase that resolved a conflict
# in a commit, or a commit the operator pushed meanwhile, counts as not rebased.
```

## `dev/agent.sh:synced`

```
# Policy: the branch follows what the operator pushes to it, by fast-forward only and only
# with nothing of its own in the way, or else by the agent's merge; a fetch that fails is
# tried again at the next turn's start, and a branch deleted on origin is followed no more.
# One rebased over what it pushed before isn't merged back into it: pushed pushes it over.
```

## `dev/agent.sh:turn-end`

```
# Policy: turn-end has the turn go on to set right what it found, but only once a turn,
# lest the turn never end.
```

## `dev/agent.sh:turn-start`

```
# Policy: work refused stays refused till what the session starts on passes: each later turn
# follows what was pushed to the branch, provisions and checks again, and says which way it went.
```

## `dev/check.sh`

```
# Usage: ./dev/check.sh [check]..., from the repository's root in the dev shell with its database
# up (dev-db start). Each check tests one thing and writes nothing git tracks; the checks
# named, or all of them, run side by side, and it fails, saying which did, if any does.
# What a check that runs says is also logged to dev/state/logs/<check>.log, as dev/write.sh moves it to logs/.
```

```
# Policy: a check skipped leaves its log as the run that passed wrote it, so that a log tells of a run.
```

## `dev/check.sh:browser`

```
# Compromise: on their own, for the browser they start.
```

## `dev/check.sh:inputs`

```
# Optimization: a check that passes holds what it read as good in dev/state/<check>-good, and is
# skipped till that changes: what settings.toml's checks.inputs names for it, as a commit of the
# worktree would hold it, for stamps also the commit stamped against, and for docs also
# origin/main, which refcheck checks the commits the docs name against. Outside a git checkout,
# such as nix's, nothing is held.
# Duplication: the tree as dev/agent.sh's tree makes it, but for what checks write.
```

## `dev/check.sh:lane`

```
# Optimization: checks named together run side by side, and what each says is said in
# order once all have run.
# Accommodating for bash, which ignores errexit wherever a status is tested: each check
# runs as a process of its own, so that it still stops at its first failure.
# Dependency: frontend's check and browser's build both write
# frontend/src/lib/api/schema.d.ts (pnpm types), so they run one after the other.
```

## `dev/check.sh:relay`

```
# Accommodating for a terminal, which interrupts only its foreground process group, and for
# bash, whose background commands ignore interrupts while job control is off: each lane
# runs as a job, a process group of its own without the terminal's input, and relay hands
# it what this gets, then waits for it to stop at the end of its check.
```

## `dev/check.sh:spooled`

```
# Duplication: dev/src/chatddx_dev/costs/__init__.py:Cost reads these columns, in this order; it
# spools them likewise only in a checkout, as told by dev/costs.tsv being there.
```

## `dev/check.sh:stamps`

```
# Compromise: the prose is checked only against a commit known to be stamped, lest a guess
# refuse work for what a write would only stamp again.
```

## `dev/dev-db.sh:CHATDDX_PGDATA`

```
# shellcheck shell=bash
```

## `dev/operator.sh`

```
# shellcheck source=dev/settings.sh
```

## `dev/operator.sh:merge`

```
# shellcheck disable=SC2064
```

## `dev/operator.sh:stamp`

```
# Policy: refs/stamped/<branch> marks what was stamped, for dev/stamped.sh to stamp against.
```

## `dev/settings.sh:setting`

```
# shellcheck shell=bash
# Usage: . dev/settings.sh, then setting <array> <key>, from the repository's root: sets the array to the words
# settings.toml holds at the dotted key.
```

```
# shellcheck disable=SC2034
```

## `dev/src/chatddx_dev/project.py:PACKAGES`

```
# Policy: where each package's top-level modules are, from the repository's root.
```

## `dev/stamped.sh:stamped`

```
# shellcheck shell=bash
# Usage: . dev/stamped.sh, from the repository's root, then stamped [guessed]: prints the commit stamps are made
# against: $STAMPED, or else what refs/stamped/<branch> holds, as ./dev/operator.sh stamp sets it, while HEAD is on it.
# Given guessed, it falls back to where HEAD left main, and fails, saying why, if there is none either. Outside a git
# checkout it prints nothing.
# Policy: the guess errs on stamping again: main is stamped, as ./dev/operator.sh merge squashes onto it, and where HEAD
# left it comes before anything stamped on the branch, so that what was stamped since is stamped again, not left out.
```

## `dev/test/stamped.bats:setup`

```
# shellcheck source=dev/stamped.sh
```

## `dev/write.sh`

```
# Usage: [STAMPED=<commit>] ./dev/write.sh [write]..., from the repository's root in the dev
# shell. Writes the writes named, or all of them, one after the other in the order of WRITES,
# what follows from the code and the docs, and says what it wrote, stopping at the first that
# fails. Each but costs and logs writes what the check of its name checks; stamps writes the
# prose's against the commit dev/stamped.sh tells, or guesses.
```

## `dev/write.sh:logs`

```
# Duplication: dev/agent.sh:moved_logs.
```
