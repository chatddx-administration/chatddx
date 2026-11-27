# Index

An index is written from a part's code, whatever its language, a doc of each kind named after the part, from the stage
`settings.toml`'s `[stamped_from]` names, with what changed in it as stamps pending:

- `docs/surfaces/<part>.md`: its public names, a module's exports and a component's props, a command's usage and a
  sourced script's functions, with a legend for each language's entries.
- `docs/comments/<part>.md`: its comments, each under the name it is in or right above.
- `docs/whoopses/<part>.md`: its `raise Whoops` and `assert` statements, its tests left out.
- `docs/catalog/<part>.md`: the messages it says, under each file that says them, with their context and plural.

`chatddx-dev index [--check] [--part <part>]... [catalog|comments|surfaces|whoopses]...` writes them, or checks them
and, of all of them, flags what the parts hold amiss: code no part holds, or two do, or that isn't there, and docs no
part has or writes.

An index is written from each file's facts (`dev/src/chatddx_dev/index/facts.py:Facts`), which
`chatddx-dev facts <file>...` prints as JSON: the names it defines and the lines they span, its comments, its claims and
its surface's entries, each entry rendered by the extractor of its language: Python's in the process with griffe, bash's
and bats' with `shfmt --to-json`, TypeScript's and Svelte's with their own parsers by `frontend/scripts/facts.mjs`. A
part's files are what git keeps or would add under its code, so that what a tool writes and git ignores is left out, as
is what `[index] left_out` names: code copied in as its makers write it.

The catalog is the scenario index (`docs/parts/locale.md`, "The scenario index"), what a person can be told, a message
an entry, written from what `chatddx locale write` extracts for the locale's catalogs
(`src/chatddx/locale/locale.py:extracted`), the whole code read once: the portal's pages, islands and Python, and
wherever in `src/chatddx/` a whoops, a finding or a refusal is worded. A locale's catalog,
`src/chatddx/locale/catalogs/<tag>.po`, is its translation. What is said as it comes, unworded, isn't in it.
