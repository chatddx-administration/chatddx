# Agent instructions
This document contains project-wide instructions written by humans for agents. Agents may append proposed amendments.

## Environment
* `.env-example` is complete and should match your environment as is, report surprises as proposed amendments.
* Human devenv is declared in flake.nix's devShell
* PostgreSQL 16
* Base the fake vLLM on 0.24.0, extend/amend continuously as new facts are discovered, questions arise or sample data is needed.

## Settings
`chatddx.core.settings` are the project-wide source of truths.

Django is used for ORM (throughout) and admin (portal only)
* `chatddx.django.settings` is the minimal, project-wide, settings needed for django orm.
* `chatddx.django.settings.portal` is for the portal and nothing outside should depend on it.

## Typechecking
* Use `pyright: basic` for django code only
* Errors and warnings that indicate issues beyond the scope of the current task should remain, don't hide them.

## Testing
* Baseline is two runs: `pytest -m "not network"` and `pytest -m "not network" --ds chatddx.django.settings.portal`
* Quick runs: add `and not slow`, `--reuse-db` keeps the test database between runs (`--create-db` once a migration changes)

### Inventory
Seeding configurations has a dedicated infrastructure: the `inventory`, with tomls, a parser and the commands `init-data`/`wipe-data`.
Tests share one inventory, `src/chatddx/data/test-inventory.toml`, and its giftbag, through the fixtures in `src/chatddx/conftest.py`.
Alice is seeded once per session and every test starts from that seed and rolls back to it.

* `recommit` varies an archived branch,
* `provision` seeds another user,
* `unseeded` empties the database for a test of seeding itself,
* `say_as` speaks to a repl through the fake vLLM
* A test without a database reads the inventory parsed (`test_inventory`).
* One slow test alone provisions the live inventory, this is by design.

### Seeding history
History is seeded by making runs against the fake vLLM.
* `chatddx samples OWNER` currently makes three runs: a typical, a broken and a rich (eventful+verbose).

## Docs
For docs in (`docs/*`), the same rule applies as to this document: Humans write, agents propose.
* Proposals are always added at the end under a section "Proposed amendments", create the section if it doesn't exist, move it to the end if it appears elsewhere.
* For each proposal include name, datetime, reason and permalinks to related material.
* Docs refer to the code, the code speaks for itself. Always remove docstrings or comments that references docs or explains what the code does before committing.
* Important details that can't be learned by reading the code+tests may deserve a comment iff it is relevant to exactly one line or section in the code, otherwise it should be added as a proposed amendment referring to the parts of the code affected by it.
* If a section of code is related to another section of code elsewhere such that reading both make them easier to understand, a path in a comment can act as a link for agents and humans alike. A comment linking two or more pieces of code this way with a short explanation is allowed.
* `agents/*` are exempt from the "Humans write, agents propose` rule and agents are free to use it for whatever purpose they deem fit.

## Misc
* Identity resolution throughout the app uses Identity.name == request.user.username, not the auth_user FK.
* For placeholder usernames in docs and tests, use alice, bob, carol... or semantic names (archive, guest, nobody, other, collaborator-one, admin),
* Besides the proxy-models' verbose_name and verbose_name_plural, never put help_text or any other user facing data in django models or migrations.
