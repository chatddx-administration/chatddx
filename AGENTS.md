Devenv in flake.nix devShell

PostgreSQL 17 always

Baseline: `pytest -m "not network"`

Use `pyright: basic` for django code

The worker is `chatddx worker serve` (a pass every time a run is queued, and a
sweep every minute). `chatddx worker run` does one pass by hand. In production a
host runs `packages.<system>.worker` from flake.nix -- `chatddx-worker`,
`serve` under another name -- as a service beside Django, with the same
environment Django gets.

Lessons:
* Never put help_text or any other user facing data in django models or migrations.
* Identity resolution throughout the app uses Identity.name == request.user.username, not the auth_user FK.
* Click/Typer quirk: any option passed after owner, even on unmodified code, breaks positional parsing.
* What a queryset annotates is declared on the model it lands on, as a
  `BranchRef` (`django/orm/annotations.py`), never as a string spelled once in
  an `annotate()` and again in a `getattr`. `django/orm/qs.py` only says which
  refs a page wants.
