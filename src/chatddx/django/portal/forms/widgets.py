# src/chatddx/django/portal/forms/widgets.py
from typing import Any

from unfold.widgets import UnfoldAdminSelect2Widget

TEMPLATE_FIELD_CSS_CLASS = "chatddx-template-field"


class TemplateSelectWidget(UnfoldAdminSelect2Widget):
    def __init__(self, attrs: dict[str, Any] | None = None, choices: Any = ()):
        attrs = dict(attrs or {})
        attrs["class"] = f"{TEMPLATE_FIELD_CSS_CLASS} {attrs.get('class', '')}".strip()

        super().__init__(attrs, choices)
