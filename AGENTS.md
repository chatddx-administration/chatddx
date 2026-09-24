NOTE:
The project is under a heavy refactor, only repo/* is instructive, the rest is relying on remnants from the past.
Meanwhile, interim baseline is currently `pytest src/chatddx/repo src/chatddx/core/tests/test_provisioning.py src/chatddx/core/tests/test_repl.py src/chatddx/runtime/tests/test_resolution.py src/chatddx/runtime/tests/test_trial.py src/chatddx/dx src/chatddx/history`

Devenv in flake.nix devShell

PostgreSQL 16 always

Baseline: `pytest -m "not network"` (temporary broken, see NOTE)

Use `pyright: basic` for django code

Lessons:
* Never put help_text or any other user facing data in django models or migrations.
* Identity resolution throughout the app uses Identity.name == request.user.username, not the auth_user FK.
