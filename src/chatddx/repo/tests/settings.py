"""
Django settings for testing chatddx.repo on its own, and the commands that
provision it:

    pytest --ds=chatddx.repo.tests.settings src/chatddx/repo
    pytest --ds=chatddx.repo.tests.settings src/chatddx/core/tests/test_provisioning.py

The rest of the project still speaks the old model: history's runs and
experiments and the portal's pages import entities the registry no longer
has. So these settings install only what the registry needs, its own models
and the identities and tags its branches hang off, under the app label the
models declare. Their tables are made straight from the models, without
migrations.
"""

import os

SECRET_KEY = "chatddx-repo-tests"
SALT_KEY = SECRET_KEY

USE_TZ = True
TIME_ZONE = "Europe/Stockholm"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.postgres",
    "chatddx.repo.tests.orm.apps.RepoOrmConfig",
]

# An app made without migrations can't depend on one made with them, and an
# identity depends on auth's user: every table comes straight from the models.
MIGRATION_MODULES = {"auth": None, "contenttypes": None, "orm": None}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "chatddx"),
        "USER": os.environ.get("DB_USER", ""),
        "HOST": os.environ.get("DB_HOST", ""),
    },
}
