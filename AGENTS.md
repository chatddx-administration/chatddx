Devenv in flake.nix devShell

PostgreSQL 16 always

Baseline: `pytest -m "not network"`

Use `pyright: basic` for django code

Lessons:
* Never put help_text or any other user facing data in django models or migrations.
* Identity resolution throughout the app uses Identity.name == request.user.username, not the auth_user FK.
* What a queryset annotates is declared on the model it lands on, as a
  `BranchRef` (`django/orm/annotations.py`), never as a string spelled once in
  an `annotate()` and again in a `getattr`. `django/orm/qs.py` only says which
  refs a page wants.
