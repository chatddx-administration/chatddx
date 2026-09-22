# pyright: basic

from typing import Any

from django.db.models import Model
from django.urls import reverse
from django.utils.http import urlencode
from unfold.utils import format_html

LINK_CLASS = "chatddx-link"


def link(url: str, label: Any):
    return format_html('<a class="{}" href="{}">{}</a>', LINK_CLASS, url, label)


def admin_url(model: type[Model] | Model, view: str, *args: Any, **params: Any) -> str:
    meta = model._meta  # pyright: ignore[reportPrivateUsage]
    url = reverse(f"admin:{meta.app_label}_{meta.model_name}_{view}", args=args)

    return f"{url}?{urlencode(params)}" if params else url


def change_link(obj: Model, label: Any = None, **params: Any):
    url = admin_url(obj, "change", obj.pk, **params)

    return link(url, obj if label is None else label)


def add_link(model: type[Model], label: Any, **params: Any):
    return link(admin_url(model, "add", **params), label)
