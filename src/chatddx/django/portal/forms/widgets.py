# src/chatddx/django/portal/forms/widgets.py
from typing import Any

from unfold.widgets import UnfoldAdminSelect2Widget

# The one CSS hook every "Template" field shares -- see
# django/portal/static/css/template_field.css, the single file that decides
# what it actually looks like.
TEMPLATE_FIELD_CSS_CLASS = "chatddx-template-field"


class TemplateSelectWidget(UnfoldAdminSelect2Widget):
    """The widget behind every branch form's `template` field -- Agent,
    Connection, Sampling Params, Output Type, Tool, Tool Group and Case all
    have one (see e.g. AgentForm.template in forms/agent.py). It's the same
    Select2 dropdown as any other relation field, just marked so it can be
    given a look of its own -- distinct from the fields it's about to
    populate -- in one shared place instead of per form.
    """

    def __init__(self, attrs: dict[str, Any] | None = None, choices: Any = ()):
        attrs = dict(attrs or {})
        attrs["class"] = f"{TEMPLATE_FIELD_CSS_CLASS} {attrs.get('class', '')}".strip()

        super().__init__(attrs, choices)
