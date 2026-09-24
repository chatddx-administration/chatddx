# pyright: basic
import os

DJANGO_MODE = os.environ.get("CHATDDX_MODE") or os.environ.get(
    "DJANGO_MODE", "default_value"
)

match DJANGO_MODE:
    case "main":
        from chatddx.django.settings.base import *  # pyright: ignore[reportWildcardImportFromLibrary]
        from chatddx.django.settings.prod import *  # pyright: ignore[reportWildcardImportFromLibrary]
        from chatddx.django.settings.unfold import *  # pyright: ignore[reportWildcardImportFromLibrary]
    case "dev":
        from chatddx.django.settings.base import *  # pyright: ignore[reportWildcardImportFromLibrary]
        from chatddx.django.settings.dev import *  # pyright: ignore[reportWildcardImportFromLibrary]
        from chatddx.django.settings.unfold import *  # pyright: ignore[reportWildcardImportFromLibrary]
    case "collectstatic":
        pass
    case _:
        raise Exception(f"Unknown DJANGO_MODE {DJANGO_MODE}")

INSTALLED_APPS = [
    "unfold",
    "chatddx.django.portal",
    "chatddx.django.core.apps.CoreConfig",
    "chatddx.django.repo.apps.RepoConfig",
    "chatddx.django.history.apps.HistoryConfig",
    "modeltranslation",
    "corsheaders",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "crispy_forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
]
STATIC_ROOT = os.environ["STATIC_ROOT"]
STATIC_URL = os.environ["STATIC_URL"]
