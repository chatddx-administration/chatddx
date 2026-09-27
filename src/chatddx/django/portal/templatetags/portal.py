# pyright: basic
from typing import Any

from django import template
from django.db.models import Model
from django.utils.text import capfirst

register = template.Library()


@register.filter
def breadcrumb(title: Any) -> str:
    return str(title) if isinstance(title, Model) else str(capfirst(title))
