Devenv in flake.nix devShell

PostgreSQL 17 always

Baseline: `pytest -m "not network"`

Use `pyright: basic` for django code

Lessons:
* Never put help_text or any other user facing data in django models or migrations.
* Identity resolution throughout the app uses Identity.name == request.user.username, not the auth_user FK.
* Click/Typer quirk: any option passed after owner, even on unmodified code, breaks positional parsing.
