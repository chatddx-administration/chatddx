from django import template

register = template.Library()


@register.inclusion_tag("templates/status_badge.html")
def render_status_badge(kind_or_instance):
    kind = getattr(kind_or_instance, "kind", kind_or_instance)

    display_name = kind.capitalize() if kind else ""
    if hasattr(kind_or_instance, "get_kind_display"):
        display_name = kind_or_instance.get_kind_display()

    return {"kind": kind, "display_name": display_name}
