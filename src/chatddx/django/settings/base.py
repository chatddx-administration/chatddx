import os
from pathlib import Path

from django.utils.translation import gettext_lazy as _

STATE_DIR = Path(os.environ["STATE_DIR"])
SCHEME = os.environ["SCHEME"]
CSRF_TRUSTED_ORIGINS = os.environ["TRUSTED_ORIGINS"].split(",")
CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS
CORS_ALLOW_CREDENTIALS = True

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "chatddx.django.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [Path(__file__).parent.parent / "portal/admin"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "chatddx.django.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "HOST": os.environ["DB_HOST"],
    },
}

# The single knob for how chatty the whole application is -- Django itself,
# the chatddx code running inside it (views, admin, ...), and the pgqueuer
# worker process started by `chatddx worker run` (which also goes through
# django.setup(), and with it this LOGGING config; see
# chatddx.experiment.worker). Unset in the environment, it defaults to INFO.
CHATDDX_LOG_LEVEL = os.environ.get("CHATDDX_LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": CHATDDX_LOG_LEVEL,
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
LANGUAGES = [
    ("en", _("English")),
    ("sv", _("Swedish")),
]

TIME_ZONE = "Europe/Stockholm"

USE_I18N = True

USE_TZ = True
FORMAT_MODULE_PATH = [
    "chatddx.django.settings.formats",
]

CRISPY_TEMPLATE_PACK = "unfold_crispy"

CRISPY_ALLOWED_TEMPLATE_PACKS = ["unfold_crispy"]
