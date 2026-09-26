# pyright: basic
import os

SALT_KEY = SECRET_KEY = "insecure-key"
ROOT_URLCONF = "chatddx.django.urls"
# the lab's, for the times the repl shows and the worker logs; Django's own
# default is America/Chicago
TIME_ZONE = "Europe/Stockholm"
STATIC_ROOT = os.environ["STATIC_ROOT"]
STATIC_URL = os.environ["STATIC_URL"]

INSTALLED_APPS = [
    "chatddx.django.core",
    "chatddx.django.repo",
    "chatddx.django.history",
    "chatddx.django.worker",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.admin",
    "django.contrib.messages",
    "django.contrib.postgres",
    "django.contrib.staticfiles",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "HOST": os.environ["DB_HOST"],
    },
}
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.request",
            ],
        },
    },
]
