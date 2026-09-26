# pyright: basic
"""
The portal's settings: the minimal ones, and what serving the portal takes on
top of them. The CLI, the repl and the tests of everything but the portal
keep to the minimal ones, so nothing here reaches them.
"""

import os

from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from .base import *
from .base import DATABASES, INSTALLED_APPS

INSTALLED_APPS = [
    "chatddx.django.portal",
    # before django.contrib.admin, whose site it replaces
    "unfold",
    *INSTALLED_APPS,
    "corsheaders",
]

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

# its tests' database, apart from the one the rest's tests keep
DATABASES = {
    "default": {**DATABASES["default"], "TEST": {"NAME": "test_chatddx_portal"}}
}

# unfold's login form carries no `next`: where a login goes by default
LOGIN_REDIRECT_URL = "admin:index"

CSRF_TRUSTED_ORIGINS = os.environ["TRUSTED_ORIGINS"].split(",")
CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS
CORS_ALLOW_CREDENTIALS = True

LANGUAGE_CODE = "en-us"
LANGUAGES = [
    ("en", _("English")),
    ("sv", _("Swedish")),
]
USE_I18N = True
USE_TZ = True
FORMAT_MODULE_PATH = ["chatddx.django.settings.formats"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{validator}"}
    for validator in (
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    )
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("CHATDDX_LOG_LEVEL", "INFO"),
    },
}

match os.environ.get("DJANGO_MODE", "dev"):
    case "dev":
        DEBUG = True
    case "main":
        DEBUG = False

        with open(os.environ["SECRET_KEY_FILE"]) as f:
            SALT_KEY = SECRET_KEY = f.read()

        ALLOWED_HOSTS = ["." + os.environ["HOST"]]
        SESSION_COOKIE_SAMESITE = "Lax"
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
        SECURE_SSL_REDIRECT = True
        SECURE_CONTENT_TYPE_NOSNIFF = True
    case mode:
        raise ImproperlyConfigured(f"DJANGO_MODE is dev or main, not {mode}")


def _at(url_name: str):
    """Whether a request is at the page of `url_name`: a tab of its own."""
    return lambda request: request.resolver_match.url_name == url_name


UNFOLD = {
    "SITE_TITLE": "chatddx",
    "SITE_HEADER": "ChatDDX Portal",
    "SITE_SYMBOL": "speed",
    "SITE_URL": "/",
    "SHOW_HISTORY": False,
    "SHOW_VIEW_ON_SITE": False,
    "BORDER_RADIUS": "6px",
    "STYLES": [lambda request: static("portal/css/portal.css")],
    "COLORS": {
        "base": {
            "50": "oklch(98.5% .002 247.839)",
            "100": "oklch(96.7% .003 264.542)",
            "200": "oklch(92.8% .006 264.531)",
            "300": "oklch(87.2% .01 258.338)",
            "400": "oklch(70.7% .022 261.325)",
            "500": "oklch(55.1% .027 264.364)",
            "600": "oklch(44.6% .03 256.802)",
            "700": "oklch(37.3% .034 259.733)",
            "800": "oklch(27.8% .033 256.848)",
            "900": "oklch(21% .034 264.665)",
            "950": "oklch(13% .028 261.692)",
        },
        "primary": {
            "50": "oklch(97.7% .014 308.299)",
            "100": "oklch(94.6% .033 307.174)",
            "200": "oklch(90.2% .063 306.703)",
            "300": "oklch(82.7% .119 306.383)",
            "400": "oklch(71.4% .203 305.504)",
            "500": "oklch(62.7% .265 303.9)",
            "600": "oklch(55.8% .288 302.321)",
            "700": "oklch(49.6% .265 301.924)",
            "800": "oklch(43.8% .218 303.724)",
            "900": "oklch(38.1% .176 304.987)",
            "950": "oklch(29.1% .149 302.717)",
        },
        "font": {
            "subtle-light": "var(--color-base-500)",
            "subtle-dark": "var(--color-base-400)",
            "default-light": "var(--color-base-600)",
            "default-dark": "var(--color-base-300)",
            "important-light": "var(--color-base-900)",
            "important-dark": "var(--color-base-100)",
        },
    },
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": True,
        "navigation": [
            {
                "title": _("Lab"),
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Cases"),
                        "icon": "clinical_notes",
                        "link": reverse_lazy("admin:portal_case_changelist"),
                    },
                    {
                        "title": _("Batches"),
                        "icon": "stacks",
                        "link": reverse_lazy("admin:portal_batch_changelist"),
                    },
                ],
            },
            {
                "title": _("Admin"),
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Users"),
                        "icon": "people",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                    },
                    {
                        "title": _("Groups"),
                        "icon": "group",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                ],
            },
        ],
    },
    # the Batches' own pages: the batches, and the worker at their queue
    "TABS": [
        {
            "models": ["portal.batch"],
            "items": [
                {
                    "title": _("Batches"),
                    "link": reverse_lazy("admin:portal_batch_changelist"),
                    "active": _at("portal_batch_changelist"),
                },
                {
                    "title": _("Status"),
                    "link": reverse_lazy("admin:portal_batch_status"),
                    "active": _at("portal_batch_status"),
                },
            ],
        },
    ],
}
