NOTE:
The project is under a heavy refactor. The portal (src/chatddx/django/portal) is being ported to the new datamodel page by page, its Batch page first, from src/chatddx/django-old-ref: stale, loaded by nothing, and named only by conftest.py's collect_ignore. The API (src/chatddx/django/api) is on the new datamodel, and in the baseline.

Devenv in flake.nix devShell

PostgreSQL 16 always

Settings: `chatddx.django.settings` is minimal, for the CLI, the repl, the API and their tests; `chatddx.django.settings.portal` adds what serving the portal takes (docs/portal.md), and nothing outside the portal leans on it.

Baseline, in two runs: `pytest -m "not network"` under the minimal settings, and `pytest -m "not network" --ds chatddx.django.settings.portal`, which runs the portal's tests alone, on a test database of their own; quick: add `and not slow` to either; `--reuse-db` keeps the test database between runs (`--create-db` once a migration changes)

The repl, the API and the portal's Batch plan and run cells through one internal API, `chatddx.bench`: a Bench (the registry as an identity sees it), a Cell, and a Plan.

Use `pyright: basic` for django code

Lessons:
* Never put help_text or any other user facing data in django models or migrations.
* Identity resolution throughout the app uses Identity.name == request.user.username, not the auth_user FK.
* Tests share one test inventory, `src/chatddx/data/test-inventory.toml`, and its giftbag, through the fixtures in `src/chatddx/conftest.py`: init-data seeds it for alice once per session, and every test starts from that seed and rolls back to it. A test reads the seeded archive rather than committing the inventory again: `recommit` varies an archived branch, `provision` seeds another user, `unseeded` empties the database for a test of seeding itself, `say_as` speaks to a repl through the `fake` vLLM, and a test without a database reads the inventory parsed (`test_inventory`). One slow test alone provisions the live inventory.
* No real person's name goes in a test or a doc. The people in them come on in alphabetical order: alice, whom the seed is for and whom a repl or a client speaks as unless told otherwise, then bob, carol, dave and erin. An identity whose part matters more than who it is goes by that part (archive, guest, nobody, other).
