# settings/unfold.py

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

UNFOLD = {
    "SITE_TITLE": "chatddx",
    "SITE_HEADER": "ChatDDX Portal",
    "SITE_SUBHEADER": "Manage agent configurations",
    "SITE_DROPDOWN": [
        {
            "icon": "storefront",
            "title": "Swift UI",
            "link": "/",
        },
        # ...
    ],
    "SITE_URL": "/",
    "SITE_SYMBOL": "speed",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": False,
    "SHOW_UI_WARNINGS": False,
    "BORDER_RADIUS": "6px",
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
        "command_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": _("Navigation"),
                "separator": False,
                "collapsible": False,
                "items": [
                    {
                        "title": "Agents",
                        "icon": "precision_manufacturing",
                        "link": reverse_lazy("admin:orm_superagent_changelist"),
                    },
                    {
                        "title": "Sessions",
                        "icon": "view_timeline",
                        "link": reverse_lazy("admin:orm_session_changelist"),
                    },
                    {
                        "title": "Identities",
                        "icon": "people",
                        "link": reverse_lazy("admin:orm_identity_changelist"),
                    },
                    {
                        "title": "Tools",
                        "icon": "handyman",
                        "link": reverse_lazy("admin:orm_tool_changelist"),
                    },
                    {
                        "title": "Cases",
                        "icon": "folder_open",
                        "link": reverse_lazy("admin:orm_case_changelist"),
                    },
                    {
                        "title": "Experiments",
                        "icon": "science",
                        "link": reverse_lazy("admin:orm_experiment_changelist"),
                    },
                    {
                        "title": "Database",
                        "icon": "database",
                        "link": reverse_lazy("admin:index"),
                    },
                ],
            },
        ],
    },
    "TABS": [
        {
            "models": [
                "orm.superagent",
                "orm.sharedsuperagent",
            ],
            "items": [
                {
                    "title": "My Agents",
                    "link": reverse_lazy("admin:orm_superagent_changelist"),
                },
                {
                    "title": "Shared with Me",
                    "link": reverse_lazy("admin:orm_sharedsuperagent_changelist"),
                },
            ],
        },
        {
            "models": [
                "orm.agent",
                "orm.sharedagent",
            ],
            "items": [
                {
                    "title": "My Agents",
                    "link": reverse_lazy("admin:orm_agent_changelist"),
                },
                {
                    "title": "Shared with Me",
                    "link": reverse_lazy("admin:orm_sharedagent_changelist"),
                },
            ],
        },
        {
            "models": [
                "orm.session",
                "orm.sharedsession",
            ],
            "items": [
                {
                    "title": "My Sessions",
                    "link": reverse_lazy("admin:orm_session_changelist"),
                },
                {
                    "title": "Shared with Me",
                    "link": reverse_lazy("admin:orm_sharedsession_changelist"),
                },
            ],
        },
        {
            "models": [
                "orm.experiment",
                "orm.sharedexperiment",
            ],
            "items": [
                {
                    "title": "My Experiments",
                    "link": reverse_lazy("admin:orm_experiment_changelist"),
                },
                {
                    "title": "Shared with Me",
                    "link": reverse_lazy("admin:orm_sharedexperiment_changelist"),
                },
            ],
        },
    ],
}
