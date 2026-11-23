# Development

What `dev/` holds, the commands it runs and what they run in turn. `settings.toml` holds the settings they share.

The scripts are bash; what they parse or rewrite is Python, `chatddx-dev`, in `dev/src/chatddx_dev/`: a uv workspace
member installed beside `chatddx` in the one environment, its command `chatddx-dev index|facts|stamp|refcheck|costs`.
`chatddx` is what a host runs, without it.

## Check

`./dev/check.sh [check]...` runs the checks named, or all of them, side by side, and writes what each says to
`dev/state/logs/<check>.log`. A check that passes is skipped till what it reads changes, its log left as the run that
passed wrote it, as `settings.toml`'s `[checks.inputs]` names it, which `flake.nix` runs it on alone, and
`dev/state/<check>-good` holds it: `rm` that to run it again.

In step with the code:

- `./dev/check.sh openapi` ~1.7s, `frontend/openapi.json` against `chatddx openapi`.
- `./dev/check.sh index`, `chatddx-dev index --check`: the surfaces, comments and whoopses against the code, and what
  the parts hold amiss (`docs/parts/index.md`).
- `./dev/check.sh stamps`, `chatddx-dev stamp check`: no conflict in a doc that isn't a stamp, and
  `chatddx-dev stamp docs --check`: the stamps pending in the prose and the catalogs against the commit stamped, if
  known.
- `./dev/check.sh locale`, `chatddx locale check`: the catalogs against the code.

Left to do:

- `./dev/check.sh pending` ~4.2s, `chatddx-dev stamp pending` and `chatddx locale pending`: stamps to resolve, messages
  to translate.

All of it formatted, as `./dev/write.sh` formats it:

- `./dev/check.sh format` ~4.3s, `ruff format --check`, `chatddx-dev stamp reflow --check`, `shfmt --diff dev` and
  `taplo fmt --check`.

Each area's lint, then its tests:

- `./dev/check.sh python-lint` ~22s, `ruff check` and `basedpyright`.
- `./dev/check.sh python-tests` ~160s, `pytest -n 4`, with `src/chatddx/test/budget.py`'s budget for the slow tests.
- `./dev/check.sh frontend` ~11s, `pnpm --dir frontend check` (`svelte-check`, after `pnpm types` writes
  `frontend/src/lib/api/schema.d.ts`) and `pnpm --dir frontend test` (`vitest`).
- `./dev/check.sh dev` ~22s, `shellcheck`, `.shellcheckrc` holding what it leaves out, and `bats dev/test`.
- `./dev/check.sh docs` ~1.7s, `chatddx-dev refcheck`: broken references, commits not in main among them.

The built app in a browser:

- `./dev/check.sh browser` ~93s, `pnpm --dir frontend build`, then `pytest -m browser`.

### Narrower runs

- `pytest` runs every test but the browser tests ~220s.
- `pytest -m 'not slow'` leaves out the slowest tests, 7/8 of the time, ~43s.
- `pytest -n 4` on 4 workers, fast when nothing else runs, ~160s.
- `pytest -m browser` the browser tests, after `pnpm --dir frontend build` if the frontend changed, ~88s.
- `pnpm --dir frontend test` the frontend's tests ~2s.
- `bats dev/test` the tests of `dev/`'s scripts.

## Write

`./dev/write.sh [write]...` writes the writes named, or all of them, one after the other, what follows from the code and
the docs, and says what it wrote. Each but `costs` and `logs` writes what the check of its name checks:

- `costs`, `chatddx-dev costs write`: folds what was timed into `dev/costs.tsv`, and rewrites a `~<n>s` figure the docs
  quote once it's 1.5 times off; `settings.toml`'s `[costs]` names the machine class and the docs.
- `logs`: the check logs, moved from `dev/state/logs/` to `logs/`
- `format`:
  - Python: `ruff format`
  - Markdown, TypeScript, Svelte, CSS and JSON: `chatddx-dev stamp reflow`, prettier on what `.prettierignore` lets
    through, the frontend as `frontend/.prettierrc` says, a doc holding stamps pending a side at a time
  - bash and bats: `shfmt --write dev`, as `.editorconfig` says
  - TOML: `taplo fmt`, on what `.taplo.toml` names
- `openapi`, the OpenAPI document, `frontend/openapi.json`: `chatddx openapi`
- `locale`, the catalogs: `chatddx locale write`
- `index`, the surfaces, comments and whoopses, with what changed as stamps pending: `chatddx-dev index`
- `stamps`, the prose and the catalogs, with what changed since the commit stamped as stamps pending:
  `chatddx-dev stamp docs <commit>`

## Stamp

`chatddx-dev stamp` inserts git conflict markers between a reference and the changes since: locale catalogs, prose and
the indexes `chatddx-dev index` writes, for a human to resolve. `./dev/check.sh pending` lists them.

## Nix

`nix flake check` runs `./dev/check.sh`'s checks but `locale`, `pending` and `browser`, each on what `settings.toml`
names for it alone, `nix/test.nix`, which boots the NixOS module in a VM for its test, ~7 minutes, and
`nix/module-eval.nix`.

## CI

Main is gated twice, as there are no pull requests: before, by `./dev/operator.sh merge`, which refuses to squash onto
main what `[operator] refused_at_merge` fails on (see "Operator"), and after, by `.forgejo/workflows/checks.yml`, which
runs `nix flake check` on each push to main, the VM test included, on a Forgejo runner on a host with Nix and KVM that
registers the label `nix`. The runner's Nix store keeps what passed, so a check whose inputs didn't change costs
nothing. `browser` runs in neither: `./dev/agent.sh hand-over` runs it.

## The database

`dev-db` runs PostgreSQL 16 from `~/.local/state/dev-db/`, on a socket only. The first start creates the cluster, the
roles and the `chatddx` database:

```sh
dev-db start
dev-db status
dev-db enter    # psql as chatddx
dev-db stop     # it keeps running after you leave the shell until you stop it
dev-db reset    # stop and delete everything; the next start begins empty
```

## State

In `dev/`, `costs.tsv`, in git: what each `./dev/check.sh` check, `pnpm --dir frontend test` and each pytest run took, a
line each, as `chatddx-dev costs write` folds it in, with tab-separated columns: when, `$MACHINE_CLASS`, seconds, exit
status, how many checks ran beside it, the commit and the command. Lines are only written with `$MACHINE_CLASS` set.

In `dev/state/`, out of git:

- `turn-start`: the commit the turn started at.
- `refused`: there while work is refused, from the turn that refused it till a turn's start passes what refused it.
- `session-start`: what session-start hands the session's first turn.
- `costs-spool.tsv`: what was timed since the last fold.
- `logs/<check>.log`: what `./dev/check.sh` said for the check when it last ran it, as `./dev/write.sh` and `hand-over`
  move it to `logs/` in git.
- `<check>-good`: what `./dev/check.sh` last passed the check on: the tree a commit of the worktree would hold, for
  `stamps` also the commit stamped, and for `docs` also `origin/main`.

## Operator

In the dev shell, pulling and pushing through `as.sh` as `$CHATDDX_DEV`:

```sh
./dev/operator.sh fetch [branch]    # switch to the branch, bring it up to its tip on origin, say what is pending
./dev/operator.sh stamp [message]   # on a branch, once nothing is pending: commit as "stamp", or the message, set refs/stamped/<branch>, push both, print the revision
./dev/operator.sh merge [branch]    # once the branch is off the tip of main, switch to it and stamp it, then squash it onto main, push it, delete the branch and its refs/stamped, print its revision
```

`stamp` prints at once when nothing changed since it last stamped, as in `./dev/operator.sh stamp | osc copy`. Start the
next session at the revision it prints, with a first prompt that begins `At <revision>`. `settings.toml`'s `[operator]`
names what `fetch` tells of and `stamp` refuses on: what `turn-start` checks, so that what is stamped passes it; and
what `merge` refuses on besides, on the branch once stamped, before it squashes: a failure leaves it stamped, and main
as it was.

## Agent

All `./dev/agent.sh` exits 0 but `turn-end`, which exits 2 to have the turn go on, and says nothing unless the agent has
something to do. `settings.toml`'s `[agent]` names what it checks when.

Claude Code's hooks (`.claude/settings.json`):

- `./dev/agent.sh session-start`, as a session starts: provisions the cloud container, fetches `refs/stamped/*`, then
  refuses work on what the commit the session starts at holds: anything out of step with the code, stamps or messages
  pending, and errors of format, lint, types or references.
- `./dev/agent.sh turn-start`, as a turn starts: moves a fresh session to the commit its first prompt starts at, or
  fast-forwards to what the operator pushed, fetching `refs/stamped/*` along, and checks what that moved it to, refusing
  work on the OpenAPI document or the catalogs out of step and telling of the rest, a part's doc no part names among
  them. While work is refused, each later turn follows what was pushed to the branch, provisions and checks again as
  session-start does, and says whether work is still refused or on again: a refusal ends when what refused it passes,
  not with its turn.
- `./dev/agent.sh turn-end`, as a turn ends: unless work was refused or nothing changed since the turn started, runs
  `./dev/write.sh`, commits what that changed as `turn-end` and pushes.

Run at request "hand over":

- `./dev/agent.sh hand-over`: writes as `turn-end` does, commits all as `hand-over` and pushes, then runs the checks
  `[agent]` names for it, and commits and pushes their logs; it tells what failed, or, once all pass, what the budget
  suggests and its thanks. The stamps a session writes are the human's to resolve, and neither it nor `turn-end` tells
  of them.
