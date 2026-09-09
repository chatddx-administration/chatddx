# src/chatddx/django/settings/main.py
import os

DJANGO_MODE = os.environ["DJANGO_MODE"]

match DJANGO_MODE:
    case "main":
        from chatddx.django.settings.base import *
        from chatddx.django.settings.prod import *
        from chatddx.django.settings.unfold import *
    case "dev":
        from chatddx.django.settings.base import *
        from chatddx.django.settings.dev import *
        from chatddx.django.settings.unfold import *
    case "collectstatic":
        pass
    case _:
        raise Exception(f"Unknown DJANGO_MODE {DJANGO_MODE}")

INSTALLED_APPS = [
    "unfold",
    "chatddx.django.portal",
    "chatddx.django.orm.apps.OrmConfig",
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
