# Agent instructions

## Environment

- Hooks set you up or tell you why they didn't, `docs/parts/dev.md` breaks down every check, write and hook. Report
  friction, poor messaging and surprises.
- Archeology is not allowed unless told otherwise: the environment given has all you need.
- That `pkill -f` pattern might match your own shell.

## Checks and writes

- `./dev/check.sh [check]...` runs the checks named, or all of them, and logs each to `dev/state/logs/<check>.log`.
- `./dev/write.sh [write]...` writes what follows from the code, `turn-end` runs all of them for you.

## Session

Hooks run `./dev/agent.sh` with `session-start`, `turn-start` and `turn-end`. All silent on success, or providing
instructions for you to act on. All exit 0 except `turn-end`, which exits 2 on failure.

When asked to hand over:

1. In the files this session has touched, remove all comments and docstrings that don't pass "Comments" and
   "Docstrings", pre-existing included.
2. Run `./dev/agent.sh hand-over`, which commits and pushes, runs the checks, and commits and pushes their logs.
3. Should a check fail for something this session didn't change, or that doesn't fail again alone, push logs and await
   further instructions; likewise once fixing it keeps growing.

When asked to rebase onto main, a push with `--force-with-lease` is permitted and expected.

## Handling errors and warnings

In order of preference:

0. Let it error or warn, if it's out of scope, or its timing, fallout and message are already about right.
1. Crash at boot, if it could have been known at boot: write a check that crashes it at boot, and attach a "fix
   boot-check <boot-check>" message, should it occur at runtime.
2. Write it raw to stderr, if it needs the attention of developers or operations: minimize tampering with the message,
   maximize simplicity in handling.
3. Tell the user, if it needs their attention. Users should not be able to cause errors, so address the possibility of
   the error rather than the error. If it's not a good time for that, raise `Whoops(message, pass_on)` and move on.
   Either way, tell the user in `message` what's going on and what they can do now, and, if `Whoops`, put in `pass_on`
   what they are to pass on to developers and ops, as it is.

## Messages

Every message touched or created is tested against the scenario index, `docs/catalog/`, every part's, before it is added
(`docs/parts/locale.md`, "The scenario index"):

1. Work out the scenario the code says it in.
2. Find a message saying that scenario: its words, case and context aside.
3. Found: say that one, as it is if apt, else reworded for every code path saying it. Not found: add it, a new scenario.
4. Its case is the running text's, raised with `upfirst`/`upFirst()` where it starts a heading, a label or a sentence; a
   context only for what tells scenarios apart that Swedish says differently.

## Development stages

`settings.toml`'s `[parts.<part>]` declares each part of the project: its class, its doc, the code that makes it, and
its stage:

1. Felt - Not really anywhere but still present somehow
2. Implied - Seen only when looking for it
3. Mentioned - Expressed as a concrete need
4. Named - Greppable and referred to as `<part>`
5. Itemized - Has one or more items in `docs/backlog.md`
6. Planned - It has a doc in `docs/parts/<part>.md` that holds a concept of a plan
7. Drafted - Exists as a moving target in the code, its doc holding what's in progress
8. Solidified - Its surface stamped, its doc describing it as it is
9. Cemented: TBD
10. Protected: TBD

A move to a stage rewrites the doc for its stage, gathers (project-wide deduplication), updates references and is a
commit of its own.

## Documentation

Destructive edits are allowed: `turn-end` stamps all changes with git conflict markers for a human to resolve.

The primary document is `docs/chatddx.md`: If a contradiction to it is discovered, stop, describe the landscape and
provide options.

## Comments

- A) Every line of comment imposes a readability tax.
- B) A future reader can be saved work by knowing about non-evident details.
- ⇒ When B is considerable enough to offset A, a comment is justified.

1. Prefix with the comment's nature
2. Tell what's non-evident and only what the code doesn't already tell

## Docstrings

Public names may have a docstring that describes their cost and utility. The cost is the resources it invokes, locks it
holds and complexity of its operations. The utility is derived from its responsibility without any assumptions about the
caller.

Docstrings are stamped along with signature and raises and the docstring should read as a direct continuation of these.

- A) Every line of docstring imposes a readability tax.
- B) Callers can dodge reading the source if the docstring gives them the right idea.
- ⇒ When B outweighs A, a docstring by that amount is justified.
