NOTE:
The project is under a heavy refactor. src/chatddx/django (the portal and the API) still relies on remnants from the past, and the baseline leaves it out.

Devenv in flake.nix devShell

PostgreSQL 16 always

Baseline: `pytest -m "not network"`

Use `pyright: basic` for django code

Lessons:
* Never put help_text or any other user facing data in django models or migrations.
* Identity resolution throughout the app uses Identity.name == request.user.username, not the auth_user FK.
* Tests share one test inventory, `src/chatddx/data/test-inventory.toml`, through the fixtures in `src/chatddx/conftest.py`: repo commits it with its own inventory functions, every other package seeds it with init-data (`provision`), and a test without a database reads it parsed (`test_inventory`).
