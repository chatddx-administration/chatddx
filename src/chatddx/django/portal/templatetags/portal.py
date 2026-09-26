# pyright: basic
"""What the portal's templates say things with."""

from typing import Any

from django import template
from django.db.models import Model
from django.utils.text import capfirst

register = template.Library()


@register.filter
def breadcrumb(title: Any) -> str:
    """
    A part of the header's breadcrumb: a label capitalised, as the admin
    writes its labels, and a thing by its own name, as it is written.
    """
    return str(title) if isinstance(title, Model) else str(capfirst(title))
